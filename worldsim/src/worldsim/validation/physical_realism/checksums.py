"""Deterministic checksums for raster / vector baseline capture."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray


def array_checksum(arr: NDArray[Any], *, round_decimals: int | None = None) -> str:
    """SHA-256 of array bytes (optionally rounded float payload)."""
    a = np.ascontiguousarray(arr)
    if round_decimals is not None and np.issubdtype(a.dtype, np.floating):
        a = np.round(a.astype(np.float64), int(round_decimals))
    h = hashlib.sha256()
    h.update(str(a.dtype).encode("ascii"))
    h.update(np.asarray(a.shape, dtype=np.int64).tobytes())
    h.update(a.tobytes())
    return h.hexdigest()


def dict_checksum(payload: Mapping[str, Any]) -> str:
    """SHA-256 of canonical JSON (sorted keys)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
