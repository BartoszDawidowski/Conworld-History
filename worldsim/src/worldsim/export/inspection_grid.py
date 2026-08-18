"""Compact monthly hex inspector cube (C9). Field-major, month-major, hex, little-endian."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

INSPECTION_GRID_SCHEMA = "inspection_grid_v1"
_DTYPE = np.dtype("<f4")
_NODATA = np.float32(np.nan)

FIELDS: tuple[tuple[str, str, str], ...] = (
    ("temperature_c", "C", "Selected-month temperature"),
    ("precipitation_mm_or_proxy", "mm_declared_proxy", "Selected-month precipitation (proxy × scale)"),
    ("humidity_rh_proxy", "RH_proxy", "Selected-month humidity / RH proxy"),
)


def encode_inspection_grid(
    *,
    temperature: NDArray[np.floating],
    precipitation: NDArray[np.floating],
    humidity: NDArray[np.floating],
    precip_scale_mm: float = 200.0,
) -> tuple[bytes, dict[str, Any]]:
    """``arrays`` are ``[n_hex, months]``. Returns little-endian float32 payload + schema."""
    temp = np.asarray(temperature, dtype=np.float64)
    precip = np.asarray(precipitation, dtype=np.float64) * float(precip_scale_mm)
    humid = np.asarray(humidity, dtype=np.float64)
    if temp.ndim != 2 or precip.shape != temp.shape or humid.shape != temp.shape:
        raise ValueError("inspection fields must share shape [n_hex, months]")
    n_hex, months = int(temp.shape[0]), int(temp.shape[1])
    stacked = np.stack([temp, precip, humid], axis=0).astype(_DTYPE, copy=False)
    # field, month, hex
    payload = np.ascontiguousarray(np.transpose(stacked, (0, 2, 1)))
    raw = payload.tobytes(order="C")
    field_stride = months * n_hex * 4
    month_stride = n_hex * 4
    fields_meta: list[dict[str, Any]] = []
    for i, (fid, unit, label) in enumerate(FIELDS):
        fields_meta.append(
            {
                "id": fid,
                "label": label,
                "unit": unit,
                "dtype": "float32",
                "endian": "little",
                "scale": 1.0,
                "nodata": None,
                "offset_bytes": i * field_stride,
                "month_stride_bytes": month_stride,
                "hex_stride_bytes": 4,
            }
        )
    schema = {
        "schema": INSPECTION_GRID_SCHEMA,
        "n_hex": n_hex,
        "months": months,
        "endian": "little",
        "file": "inspection_grid.bin",
        "layout": "field_major, month_major, hex",
        "fields": fields_meta,
    }
    return raw, schema


def decode_inspection_value(
    blob: bytes,
    schema: dict[str, Any],
    field_id: str,
    *,
    month: int,
    hex_id: int,
) -> float:
    """Read one value; month is 0-based."""
    fields = {str(f["id"]): f for f in schema.get("fields", [])}
    if field_id not in fields:
        raise KeyError(field_id)
    spec = fields[field_id]
    n_hex = int(schema["n_hex"])
    months = int(schema["months"])
    if month < 0 or month >= months or hex_id < 0 or hex_id >= n_hex:
        return float("nan")
    off = int(spec["offset_bytes"]) + month * n_hex * 4 + hex_id * 4
    return float(np.frombuffer(blob, dtype=_DTYPE, count=1, offset=off)[0])


def write_inspection_grid(
    directory: Path,
    *,
    temperature: NDArray[np.floating],
    precipitation: NDArray[np.floating],
    humidity: NDArray[np.floating],
    precip_scale_mm: float = 200.0,
) -> dict[str, Any]:
    raw, schema = encode_inspection_grid(
        temperature=temperature,
        precipitation=precipitation,
        humidity=humidity,
        precip_scale_mm=precip_scale_mm,
    )
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "inspection_grid.bin").write_bytes(raw)
    (directory / "inspection_grid.json").write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return schema
