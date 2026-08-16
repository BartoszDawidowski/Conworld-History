"""Capture reproducible physical-realism baselines (PR-0).

Does not alter production physics. Writes metrics, checksums, absolute maps,
effective config, and timing / peak-RSS under an output directory.

Heavy worldsim run trees are written to a temp work directory and discarded
unless ``--keep-work`` is set.

Example::

    python -m worldsim.validation.physical_realism.capture_baseline \\
        --output docs/validation/physical_realism_pr0/baseline \\
        --profile quick --seeds 1,42,100
"""

from __future__ import annotations

import argparse
import json
import platform
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from worldsim import SCHEMA_VERSION, __version__
from worldsim.config import PlanetConfig, default_config_path, load_planet_config
from worldsim.pipeline import run_world
from worldsim.progress import ProgressReporter
from worldsim.validation.physical_realism.absolute_maps import write_absolute_scalar_png
from worldsim.validation.physical_realism.checksums import array_checksum, dict_checksum
from worldsim.validation.physical_realism.fixtures import (
    january_dry_start_ramp,
    land_max_hits_scale,
    northward_impulse_result,
    precip_vs_available_q_overshoot,
)
from worldsim.validation.physical_realism.metrics import (
    hydrology_metrics,
    land_hypsometry_metrics,
    moisture_annual_metrics,
    peak_rss_mb,
)
from worldsim.validation.physical_realism.seed_suites import (
    ATLAS_SEEDS,
    AUDIT_BASELINE_COMMIT,
    FULL_SEEDS,
    PROFILE_GRIDS,
    QUICK_SEEDS,
    REALISM_SCHEMA_VERSION,
)


def _config_snapshot(config: PlanetConfig) -> dict[str, Any]:
    return {k: v for k, v in asdict(config).items() if k != "raw"}


def _analysis_override(config: PlanetConfig, analysis: tuple[int, int]) -> PlanetConfig:
    data = asdict(config)
    data.pop("raw", None)
    data["analysis_width"] = int(analysis[0])
    data["analysis_height"] = int(analysis[1])
    data["raw"] = config.raw
    return PlanetConfig(**data)


def capture_seed(
    *,
    config: PlanetConfig,
    master_seed: int,
    output_dir: Path,
    profile: str,
    write_maps: bool,
    work_root: Path,
) -> dict[str, Any]:
    grids = PROFILE_GRIDS[profile]
    tw, th = grids["terrain"]
    cw, ch = grids["climate"]
    tec_w, tec_h = grids["tectonics"]
    aw, ah = grids["analysis"]
    cfg = _analysis_override(config, (aw, ah))

    seed_dir = output_dir / f"seed_{master_seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    run_dir = work_root / f"seed_{master_seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    rss0 = peak_rss_mb()
    reporter = ProgressReporter(stream=open("/dev/null", "w", encoding="utf-8"))
    try:
        state = run_world(
            config=cfg,
            master_seed=master_seed,
            output_dir=run_dir,
            reporter=reporter,
            width=tec_w,
            height=tec_h,
            terrain_width=tw,
            terrain_height=th,
            climate_width=cw,
            climate_height=ch,
        )
    finally:
        reporter.stream.close()
    elapsed_s = time.perf_counter() - t0
    rss1 = peak_rss_mb()

    elev = np.asarray(state.rasters["dem_v2"], dtype=np.float64)
    ocean_terrain = np.asarray(state.terrain.ocean_mask, dtype=bool)
    ocean_climate = np.asarray(state.climate.ocean_mask, dtype=bool)
    ocean = ocean_terrain if elev.shape == ocean_terrain.shape else ocean_climate

    hyp = land_hypsometry_metrics(elev, ocean)
    hyp["hits_land_scale_max"] = bool(
        np.isclose(hyp.get("max_m", 0.0), float(cfg.land_scale_m), rtol=0.0, atol=1.0)
    )

    moist = state.moisture
    precip_ann = np.asarray(moist.annual_precipitation, dtype=np.float64)
    moist_m = moisture_annual_metrics(
        precip_ann,
        ocean_climate if precip_ann.shape == ocean_climate.shape else ocean,
    )

    hydro = state.hydrology
    hydro_ocean = ocean_terrain if elev.shape == ocean_terrain.shape else ocean
    hydro_m = hydrology_metrics(
        river_mask=hydro.river_mask,
        lake_mask=hydro.lake_mask,
        flow_accumulation=hydro.flow_accumulation,
        ocean_mask=hydro_ocean,
    )

    checksums = {
        "elevation_v2_m": array_checksum(elev, round_decimals=3),
        "ocean_mask": array_checksum(ocean.astype(np.uint8)),
        "annual_precipitation": array_checksum(precip_ann, round_decimals=4),
    }
    if hydro.flow_direction is not None:
        checksums["flow_direction"] = array_checksum(
            np.asarray(hydro.flow_direction, dtype=np.uint8)
        )
    if hydro.basin_id is not None:
        checksums["basin_id"] = array_checksum(np.asarray(hydro.basin_id, dtype=np.int32))

    maps_meta: list[dict[str, Any]] = []
    if write_maps:
        maps_dir = seed_dir / "absolute_maps"
        maps_meta.append(
            write_absolute_scalar_png(
                maps_dir / "elevation_m.png",
                elev,
                lo=-6000.0,
                hi=float(cfg.land_scale_m),
                unit="m",
                ocean_mask=ocean if elev.shape == ocean.shape else None,
            )
        )
        o_mask = ocean_climate if precip_ann.shape == ocean_climate.shape else ocean
        maps_meta.append(
            write_absolute_scalar_png(
                maps_dir / "annual_precip.png",
                precip_ann,
                lo=0.0,
                hi=40.0,
                unit="moisture_proxy_annual",
                ocean_mask=o_mask,
                legend_extra={
                    "note": "Fixed absolute legend [0, 40] proxy units across seeds",
                },
            )
        )

    effective = {
        "schema_version": int(cfg.schema_version),
        "worldsim_version": __version__,
        "planet_schema_version": SCHEMA_VERSION,
        "master_seed": int(master_seed),
        "profile": profile,
        "grids": {k: list(v) for k, v in grids.items()},
        "config": _config_snapshot(cfg),
        "run_metadata": dict(state.metadata),
    }
    (seed_dir / "effective_config.json").write_text(
        json.dumps(effective, indent=2, default=str) + "\n", encoding="utf-8"
    )

    record = {
        "master_seed": int(master_seed),
        "profile": profile,
        "elapsed_s": round(elapsed_s, 3),
        "peak_rss_mb_before": rss0,
        "peak_rss_mb_after": rss1,
        "hypsometry": hyp,
        "moisture": moist_m,
        "hydrology": hydro_m,
        "checksums": checksums,
        "absolute_maps": maps_meta,
        "effective_config_checksum": dict_checksum(effective),
    }
    (seed_dir / "metrics.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return record


def capture_fixture_probes() -> dict[str, Any]:
    """Cheap synthetic probes recording current (buggy) baseline behaviour."""
    return {
        "northward_impulse": northward_impulse_result(),
        "precip_overshoot": precip_vs_available_q_overshoot(),
        "january_ramp": january_dry_start_ramp(),
        "land_max_hits_scale": land_max_hits_scale(),
    }


def capture_baseline(
    *,
    output_dir: Path,
    profile: str = "quick",
    seeds: tuple[int, ...] | None = None,
    write_maps: bool = True,
    config_path: Path | None = None,
    keep_work: bool = False,
) -> dict[str, Any]:
    if profile not in PROFILE_GRIDS:
        raise ValueError(f"unknown profile {profile!r}")
    if seeds is None:
        seeds = (
            QUICK_SEEDS
            if profile == "quick"
            else (ATLAS_SEEDS if profile == "atlas" else FULL_SEEDS)
        )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_planet_config(
        config_path if config_path is not None else default_config_path()
    )

    work_ctx: tempfile.TemporaryDirectory[str] | None = None
    if keep_work:
        work_root = output_dir / "_work"
        work_root.mkdir(parents=True, exist_ok=True)
    else:
        work_ctx = tempfile.TemporaryDirectory(prefix="physical_realism_pr0_")
        work_root = Path(work_ctx.name)

    try:
        seed_records = [
            capture_seed(
                config=config,
                master_seed=int(seed),
                output_dir=output_dir,
                profile=profile,
                write_maps=write_maps,
                work_root=work_root,
            )
            for seed in seeds
        ]
    finally:
        if work_ctx is not None:
            work_ctx.cleanup()

    probes = capture_fixture_probes()
    report: dict[str, Any] = {
        "realism_schema_version": REALISM_SCHEMA_VERSION,
        "audit_baseline_commit": AUDIT_BASELINE_COMMIT,
        "worldsim_version": __version__,
        "planet_schema_version": SCHEMA_VERSION,
        "profile": profile,
        "seeds": list(seeds),
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        "fixture_probes": probes,
        "seed_records": seed_records,
    }
    (output_dir / "baseline_report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_GRIDS.keys()),
        default="quick",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="comma-separated master seeds (default: suite for profile)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="planet YAML (default: packaged)",
    )
    parser.add_argument(
        "--no-maps",
        action="store_true",
        help="skip absolute-scale PNG export",
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="retain full worldsim run directories (large; default deletes)",
    )
    args = parser.parse_args(argv)
    seeds = None
    if args.seeds:
        seeds = tuple(int(x.strip()) for x in args.seeds.split(",") if x.strip())
    capture_baseline(
        output_dir=args.output,
        profile=args.profile,
        seeds=seeds,
        write_maps=not args.no_maps,
        config_path=args.config,
        keep_work=args.keep_work,
    )
    print(f"Wrote baseline under {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
