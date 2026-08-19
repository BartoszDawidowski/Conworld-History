"""PC7 production suite runner — seeds, maps, RSS, artifact sizes, readiness."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np

from worldsim.config import PlanetConfig, default_config_path, load_planet_config
from worldsim.pipeline import run_world
from worldsim.progress import ProgressReporter
from worldsim.spatial.canonical_acceptance import collect_gates
from worldsim.spatial.model import WorldSpatialModel
from worldsim.validation.physical_realism.absolute_maps import write_absolute_scalar_png
from worldsim.validation.physical_realism.metrics import peak_rss_mb
from worldsim.validation.production_closure.c10_readiness import review_c10_readiness
from worldsim.validation.production_closure.performance import analyze_stage_regression
from worldsim.validation.production_closure.seeds import (
    PC7_ATLAS_SEEDS,
    PC7_FULL_SEEDS,
    PC7_QUICK_SEEDS,
    PC7_SCHEMA_VERSION,
    PROFILE_GRIDS,
)


def directory_size_bytes(root: Path) -> int:
    total = 0
    for path in Path(root).rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return int(total)


def _analysis_override(config: PlanetConfig, analysis: tuple[int, int]) -> PlanetConfig:
    from dataclasses import asdict

    data = asdict(config)
    data.pop("raw", None)
    data["analysis_width"] = int(analysis[0])
    data["analysis_height"] = int(analysis[1])
    data["raw"] = config.raw
    return PlanetConfig(**data)


@dataclass
class SeedRunResult:
    profile: str
    master_seed: int
    elapsed_s: float
    peak_rss_mb_before: float | None
    peak_rss_mb_after: float | None
    artifact_bytes: int
    acceptance_ok: bool
    gates: dict[str, bool]
    stage_timings_s: dict[str, float]
    stage_peak_rss_mb: dict[str, float | None]
    precip_scale_mm: float
    absolute_maps: list[dict[str, Any]]
    output_dir: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "master_seed": self.master_seed,
            "elapsed_s": round(self.elapsed_s, 3),
            "peak_rss_mb_before": self.peak_rss_mb_before,
            "peak_rss_mb_after": self.peak_rss_mb_after,
            "artifact_bytes": self.artifact_bytes,
            "acceptance_ok": self.acceptance_ok,
            "gates": self.gates,
            "stage_timings_s": self.stage_timings_s,
            "stage_peak_rss_mb": self.stage_peak_rss_mb,
            "precip_scale_mm": self.precip_scale_mm,
            "absolute_maps": self.absolute_maps,
            "output_dir": str(self.output_dir),
        }


def run_production_seed(
    *,
    config: PlanetConfig,
    profile: str,
    master_seed: int,
    output_dir: Path,
    write_maps: bool = True,
) -> SeedRunResult:
    """Run one profile/seed through ``run_world`` and collect PC7 metrics."""
    if profile not in PROFILE_GRIDS:
        raise ValueError(f"unknown profile {profile!r}")
    grids = PROFILE_GRIDS[profile]
    tw, th = grids["terrain"]
    cw, ch = grids["climate"]
    tec_w, tec_h = grids["tectonics"]
    aw, ah = grids["analysis"]
    cfg = _analysis_override(config, (aw, ah))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rss0 = peak_rss_mb()
    reporter = ProgressReporter(stream=StringIO())
    t0 = time.perf_counter()
    try:
        state = run_world(
            config=cfg,
            master_seed=int(master_seed),
            output_dir=output_dir,
            reporter=reporter,
            width=tec_w,
            height=tec_h,
            terrain_width=tw,
            terrain_height=th,
            climate_width=cw,
            climate_height=ch,
        )
    finally:
        reporter.close()
    elapsed = time.perf_counter() - t0
    rss1 = peak_rss_mb()

    timing = dict(state.metadata.get("stage_timings_s") or {})
    peak_by_stage = dict(state.metadata.get("stage_peak_rss_mb") or {})
    world = WorldSpatialModel.load(output_dir / "world")
    report = (world.manifest.extra or {}).get("canonical_acceptance") or {}
    gates = dict(report.get("gates") or collect_gates())
    acceptance_ok = bool(world.manifest.acceptance_ok)

    maps_meta: list[dict[str, Any]] = []
    if write_maps and state.rasters.get("dem_v2") is not None:
        elev = np.asarray(state.rasters["dem_v2"], dtype=np.float64)
        ocean = np.asarray(state.terrain.ocean_mask, dtype=bool)
        maps_dir = output_dir / "absolute_maps"
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
        precip_ann = np.asarray(state.moisture.annual_precipitation, dtype=np.float64)
        o_mask = (
            np.asarray(state.climate.ocean_mask, dtype=bool)
            if precip_ann.shape == state.climate.ocean_mask.shape
            else ocean
        )
        maps_meta.append(
            write_absolute_scalar_png(
                maps_dir / "annual_precip.png",
                precip_ann,
                lo=0.0,
                hi=40.0,
                unit="moisture_proxy_annual",
                ocean_mask=o_mask,
                legend_extra={
                    "note": "Fixed absolute legend [0, 40] proxy units (PC7 cross-seed)",
                },
            )
        )

    return SeedRunResult(
        profile=profile,
        master_seed=int(master_seed),
        elapsed_s=elapsed,
        peak_rss_mb_before=rss0,
        peak_rss_mb_after=rss1,
        artifact_bytes=directory_size_bytes(output_dir),
        acceptance_ok=acceptance_ok,
        gates=gates,
        stage_timings_s=timing,
        stage_peak_rss_mb=peak_by_stage,
        precip_scale_mm=float(cfg.precip_scale_mm),
        absolute_maps=maps_meta,
        output_dir=output_dir,
    )


def cross_profile_physical_scale(
    *,
    config: PlanetConfig,
    seed: int,
    work_root: Path,
    write_maps: bool = False,
) -> dict[str, Any]:
    """Compare fixed-scale metrics for the same seed on quick vs atlas grids."""
    work_root = Path(work_root)
    quick = run_production_seed(
        config=config,
        profile="quick",
        master_seed=seed,
        output_dir=work_root / f"cross_quick_{seed}",
        write_maps=write_maps,
    )
    atlas = run_production_seed(
        config=config,
        profile="atlas",
        master_seed=seed,
        output_dir=work_root / f"cross_atlas_{seed}",
        write_maps=write_maps,
    )
    return {
        "seed": int(seed),
        "precip_scale_mm_consistent": float(quick.precip_scale_mm)
        == float(atlas.precip_scale_mm),
        "precip_scale_mm": float(quick.precip_scale_mm),
        "quick_elapsed_s": quick.elapsed_s,
        "atlas_elapsed_s": atlas.elapsed_s,
        "quick_acceptance_ok": quick.acceptance_ok,
        "atlas_acceptance_ok": atlas.acceptance_ok,
        "quick_gates": quick.gates,
        "atlas_gates": atlas.gates,
        "quick_artifact_bytes": quick.artifact_bytes,
        "atlas_artifact_bytes": atlas.artifact_bytes,
    }


def build_pc7_report(
    *,
    seed_results: list[SeedRunResult],
    cross_profile: dict[str, Any] | None = None,
    full_smoke: SeedRunResult | None = None,
) -> dict[str, Any]:
    """Assemble the PC7 suite artefact for docs and CI."""
    suite_ok = bool(seed_results)
    reference = seed_results[-1] if seed_results else None
    performance = analyze_stage_regression(
        reference.stage_timings_s if reference else {},
        total_elapsed_s=reference.elapsed_s if reference else None,
    )
    gates = dict(reference.gates if reference else {})
    readiness = review_c10_readiness(
        gates=gates,
        suite_ok=suite_ok,
        performance_documented=True,
    )
    return {
        "schema_version": PC7_SCHEMA_VERSION,
        "seeds": {
            "quick": [r.to_dict() for r in seed_results if r.profile == "quick"],
            "atlas": [r.to_dict() for r in seed_results if r.profile == "atlas"],
            "full": [full_smoke.to_dict()] if full_smoke else [],
        },
        "cross_profile": cross_profile or {},
        "performance": performance,
        "c10_readiness": readiness,
        "artifact_summary": {
            "total_runs": len(seed_results) + (1 if full_smoke else 0),
            "max_artifact_bytes": max(
                [r.artifact_bytes for r in seed_results]
                + ([full_smoke.artifact_bytes] if full_smoke else [0])
            ),
        },
    }


def run_pc7_suite(
    *,
    output_dir: Path,
    config_path: Path | None = None,
    include_full: bool = False,
    include_cross_profile: bool = False,
    write_maps: bool = True,
) -> dict[str, Any]:
    """Execute the required PC7 seed matrix and write ``pc7_report.json``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_planet_config(
        config_path if config_path is not None else default_config_path()
    )
    results: list[SeedRunResult] = []
    for seed in PC7_QUICK_SEEDS:
        results.append(
            run_production_seed(
                config=config,
                profile="quick",
                master_seed=seed,
                output_dir=output_dir / "quick" / f"seed_{seed}",
                write_maps=write_maps,
            )
        )
    for seed in PC7_ATLAS_SEEDS:
        results.append(
            run_production_seed(
                config=config,
                profile="atlas",
                master_seed=seed,
                output_dir=output_dir / "atlas" / f"seed_{seed}",
                write_maps=write_maps,
            )
        )
    full_smoke: SeedRunResult | None = None
    if include_full:
        full_smoke = run_production_seed(
            config=config,
            profile="full",
            master_seed=PC7_FULL_SEEDS[0],
            output_dir=output_dir / "full" / f"seed_{PC7_FULL_SEEDS[0]}",
            write_maps=write_maps,
        )
    cross: dict[str, Any] | None = None
    if include_cross_profile:
        cross = cross_profile_physical_scale(
            config=config,
            seed=42,
            work_root=output_dir / "cross_profile",
            write_maps=write_maps,
        )
    report = build_pc7_report(
        seed_results=results,
        cross_profile=cross,
        full_smoke=full_smoke,
    )
    (output_dir / "pc7_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return report


def default_config_path_for_suite() -> Path:
    return default_config_path()
