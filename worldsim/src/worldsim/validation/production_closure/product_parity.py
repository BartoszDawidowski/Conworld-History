"""PC6 — save/load/re-export parity probes for canonical products."""

from __future__ import annotations

from typing import Any

import numpy as np

from worldsim.export.atlas_display import export_atlas_display
from worldsim.spatial.hex_grid.contract import hex_environment_columns
from worldsim.spatial.model import WorldSpatialModel
from worldsim.spatial.product_contracts import (
    CHANNEL_TIER_RASTERS,
    HEX_EXPORT_COLUMN_FIELDS,
    HEX_EXPORT_CONTRACT_FIELDS,
    PERSISTED_CRYOSPHERE_RASTERS,
    PERSISTED_HYDROLOGY_RASTERS,
    PRODUCT_CONTRACT_VERSION,
)


def tier_mask_counts(model: WorldSpatialModel) -> dict[str, int]:
    out: dict[str, int] = {}
    for key in CHANNEL_TIER_RASTERS:
        if not model.rasters.has(key):
            out[key] = -1
            continue
        arr = np.asarray(model.rasters.get(key))
        out[key] = int(np.count_nonzero(arr))
    return out


def raster_parity(model: WorldSpatialModel, loaded: WorldSpatialModel) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for key in (*PERSISTED_HYDROLOGY_RASTERS, *PERSISTED_CRYOSPHERE_RASTERS):
        if not model.rasters.has(key):
            checks[key] = not loaded.rasters.has(key)
            continue
        if not loaded.rasters.has(key):
            checks[key] = False
            continue
        checks[key] = bool(
            np.array_equal(
                np.asarray(model.rasters.get(key)),
                np.asarray(loaded.rasters.get(key)),
            )
        )
    return checks


def hex_contract_parity(model: WorldSpatialModel) -> dict[str, Any]:
    """Atlas hex export columns must match the shared C8 contract."""
    cols = hex_environment_columns(model.hex_grid)
    exported = list(cols.keys())
    missing = [f for f in HEX_EXPORT_COLUMN_FIELDS if f not in exported]
    extra = [f for f in exported if f not in HEX_EXPORT_COLUMN_FIELDS]
    return {
        "contract_version": PRODUCT_CONTRACT_VERSION,
        "missing_fields": missing,
        "unexpected_fields": extra,
        "ok": not missing,
    }


def save_load_parity_probe(model: WorldSpatialModel, root) -> dict[str, Any]:
    """Save, reload, and compare tier masks + hex contract."""
    from pathlib import Path

    root = Path(root)
    model.save(root)
    loaded = WorldSpatialModel.load(root)
    raster_checks = raster_parity(model, loaded)
    return {
        "product_contract_version": PRODUCT_CONTRACT_VERSION,
        "raster_parity": raster_checks,
        "raster_parity_ok": all(raster_checks.values()),
        "tier_counts_before": tier_mask_counts(model),
        "tier_counts_after": tier_mask_counts(loaded),
        "hex_contract": hex_contract_parity(model),
    }


def reexport_parity_probe(model: WorldSpatialModel, directory) -> dict[str, Any]:
    from pathlib import Path

    directory = Path(directory)
    meta = export_atlas_display(model, directory)
    return {
        "atlas_schema": meta.get("schema"),
        "inspector_contract_version": meta.get("inspector_contract_version"),
        "hex_contract_fields_ok": list(meta.get("hex_contract_fields") or [])
        == list(HEX_EXPORT_CONTRACT_FIELDS),
        "diagnostic_layer_ids": list(meta.get("diagnostic_layer_ids") or []),
    }
