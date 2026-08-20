"""PC6 — resolve and persist effective physical + display configuration."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from worldsim import SCHEMA_VERSION, __version__
from worldsim.config import PlanetConfig
from worldsim.validation.physical_realism.checksums import dict_checksum

EFFECTIVE_CONFIG_SCHEMA_VERSION = "pc6_effective_config_v1"


def _config_snapshot(config: PlanetConfig) -> dict[str, Any]:
    return {k: v for k, v in asdict(config).items() if k != "raw"}


def _param_group(config: PlanetConfig, name: str) -> dict[str, Any]:
    converter = {
        "hydrology_physics": config.to_hydrology_params,
        "moisture_physics": config.to_moisture_params,
        "erosion_physics": config.to_erosion_params,
        "final_erosion_physics": config.to_final_recalc_params,
        "landform_classification": config.to_landform_params,
        "ecology_physics": config.to_ecology_params,
    }[name]
    return asdict(converter())


def build_effective_config(
    *,
    config: PlanetConfig,
    master_seed: int,
    grids: dict[str, list[int] | tuple[int, ...]] | None = None,
    run_metadata: dict[str, Any] | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Canonical effective values for save/load, Godot Advanced, and PC7 baselines."""
    grid_payload: dict[str, list[int]] = {}
    if grids:
        for key, size in grids.items():
            grid_payload[str(key)] = [int(size[0]), int(size[1])]

    display_lod = {
        "river_acc_fraction": float(config.hydrology_river_acc_fraction),
        "river_discharge_candidate_quantile": float(
            config.hydrology_river_discharge_candidate_quantile
        ),
        # precip_scale_mm is NOT display-only: it scales ecology, runoff, Q, and
        # lake storage. Kept under physical_groups.ecology_physics below.
    }

    return {
        "effective_config_schema_version": EFFECTIVE_CONFIG_SCHEMA_VERSION,
        "schema_version": int(config.schema_version),
        "worldsim_version": __version__,
        "planet_schema_version": SCHEMA_VERSION,
        "master_seed": int(master_seed),
        "profile": profile,
        "grids": grid_payload,
        "config": _config_snapshot(config),
        "physical_groups": {
            "hydrology_physics": _param_group(config, "hydrology_physics"),
            "lake_storage": {
                "lake_storage_spinup_years": int(
                    config.to_hydrology_params().lake_storage_spinup_years
                ),
                "lake_storage_spinup_tol": float(
                    config.to_hydrology_params().lake_storage_spinup_tol
                ),
                "runoff_spinup_years": int(config.to_hydrology_params().runoff_spinup_years),
                "runoff_spinup_tol": float(config.to_hydrology_params().runoff_spinup_tol),
            },
            "snow_firn_foundation": {
                "snow_threshold_c": float(config.to_hydrology_params().snow_threshold_c),
                "snow_band_c": float(config.to_hydrology_params().snow_band_c),
                "melt_factor_per_c": float(config.to_hydrology_params().melt_factor_per_c),
                "max_snow_store": float(config.to_hydrology_params().max_snow_store),
                "soil_capacity": float(config.to_hydrology_params().soil_capacity),
                "soil_quickflow_frac": float(
                    config.to_hydrology_params().soil_quickflow_frac
                ),
            },
            "erosion_physics": _param_group(config, "erosion_physics"),
            "final_erosion_physics": _param_group(config, "final_erosion_physics"),
            "landform_classification": _param_group(config, "landform_classification"),
            "moisture_physics": _param_group(config, "moisture_physics"),
            "ecology_physics": _param_group(config, "ecology_physics"),
        },
        "display_only_lod": display_lod,
        "run_metadata": dict(run_metadata or {}),
    }


def effective_config_checksum(payload: Mapping[str, Any]) -> str:
    """Checksum excluding any pre-existing checksum field."""
    clean = dict(payload)
    clean.pop("effective_config_checksum", None)
    return dict_checksum(clean)


def write_effective_config(path: Path, payload: dict[str, Any]) -> str:
    """Write ``effective_config.json``; return checksum."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    checksum = effective_config_checksum(payload)
    out = dict(payload)
    out["effective_config_checksum"] = checksum
    path.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return checksum
