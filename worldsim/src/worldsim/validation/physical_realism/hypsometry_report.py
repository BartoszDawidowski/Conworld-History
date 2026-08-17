"""Seed-suite hypsometry before/after report for PR-2 (no folding retune)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from worldsim.config import default_config_path, load_planet_config
from worldsim.physical.tectonics import run_pyplatec_extended
from worldsim.physical.tectonics.interpretation import run_tectonic_interpretation
from worldsim.physical.terrain import TerrainParams, build_terrain_ocean
from worldsim.validation.physical_realism.absolute_maps import write_absolute_scalar_png
from worldsim.validation.physical_realism.seed_suites import QUICK_SEEDS


def _run_mode(
    *,
    seed: int,
    mode: str,
    width: int,
    height: int,
    tec_w: int,
    tec_h: int,
    config,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    tectonics = run_pyplatec_extended(
        seed=seed,
        width=tec_w,
        height=tec_h,
        params=config.to_pyplatec_params(),
    )
    interpretation = run_tectonic_interpretation(tectonics)
    terrain = build_terrain_ocean(
        tectonics=tectonics,
        interpretation=interpretation,
        params=TerrainParams(
            width=width,
            height=height,
            ocean_fraction_target=config.ocean_fraction_target,
            detail_amplitude=config.terrain_detail_amplitude,
            land_scale_m=config.land_scale_m,
            ocean_scale_m=config.ocean_scale_m,
            orogeny_boost=config.orogeny_boost,
            activity_relief=config.activity_relief,
            boundary_relief=config.boundary_relief,
            hypsometry_mode=mode,
            hypsometry_anchor_quantile=config.hypsometry_anchor_quantile,
            hypsometry_anchor_elevation_m=config.hypsometry_anchor_elevation_m,
            hypsometry_body_exponent=config.hypsometry_body_exponent,
            hypsometry_max_elevation_m=config.hypsometry_max_elevation_m
            or config.land_scale_m,
            hypsometry_tail_softness=config.hypsometry_tail_softness,
        ),
        detail_seed=seed * 17 + 3,
    )
    elapsed = time.perf_counter() - t0
    return {
        "master_seed": seed,
        "mode": mode,
        "elapsed_s": round(elapsed, 3),
        "folding_ratio": float(config.tectonics_folding_ratio),
        "land_hypsometry": terrain.diagnostics.get("land_hypsometry"),
        "hypsometry": terrain.diagnostics.get("hypsometry"),
        "rank_order_ok": terrain.diagnostics.get("rank_order_ok"),
        "land_components_unchanged": terrain.diagnostics.get(
            "land_components_unchanged"
        ),
        "elevation_m": terrain.elevation_m,
        "ocean_mask": terrain.ocean_mask,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=str, default="1,42,100")
    parser.add_argument("--terrain-width", type=int, default=256)
    parser.add_argument("--terrain-height", type=int, default=128)
    parser.add_argument("--tectonics-width", type=int, default=128)
    parser.add_argument("--tectonics-height", type=int, default=64)
    args = parser.parse_args(argv)

    seeds = tuple(int(x.strip()) for x in args.seeds.split(",") if x.strip())
    if not seeds:
        seeds = QUICK_SEEDS
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    config = load_planet_config(default_config_path())

    records: list[dict[str, Any]] = []
    for seed in seeds:
        legacy = _run_mode(
            seed=seed,
            mode="legacy_max",
            width=args.terrain_width,
            height=args.terrain_height,
            tec_w=args.tectonics_width,
            tec_h=args.tectonics_height,
            config=config,
        )
        v2 = _run_mode(
            seed=seed,
            mode="power_tail_v2",
            width=args.terrain_width,
            height=args.terrain_height,
            tec_w=args.tectonics_width,
            tec_h=args.tectonics_height,
            config=config,
        )
        seed_dir = out / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        write_absolute_scalar_png(
            seed_dir / "elevation_legacy_m.png",
            legacy["elevation_m"],
            lo=-6000.0,
            hi=float(config.land_scale_m),
            unit="m",
            ocean_mask=legacy["ocean_mask"],
        )
        write_absolute_scalar_png(
            seed_dir / "elevation_power_tail_v2_m.png",
            v2["elevation_m"],
            lo=-6000.0,
            hi=float(config.land_scale_m),
            unit="m",
            ocean_mask=v2["ocean_mask"],
        )
        # Drop heavy arrays from JSON
        for rec in (legacy, v2):
            rec.pop("elevation_m", None)
            rec.pop("ocean_mask", None)
        records.append({"legacy_max": legacy, "power_tail_v2": v2})

    maxima_v2 = [
        r["power_tail_v2"]["land_hypsometry"].get("max_m") for r in records
    ]
    report = {
        "milestone": "PR-2",
        "folding_ratio_frozen": float(config.tectonics_folding_ratio),
        "seeds": list(seeds),
        "terrain_resolution": [args.terrain_width, args.terrain_height],
        "power_tail_maxima_m": maxima_v2,
        "maxima_mechanically_identical": bool(
            len({round(float(m), 1) for m in maxima_v2 if m is not None}) <= 1
        ),
        "records": records,
    }
    (out / "hypsometry_seed_report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out / 'hypsometry_seed_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
