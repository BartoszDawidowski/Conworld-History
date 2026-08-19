"""Frozen Atlas production baselines for PC0 regression tracking."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_BASELINE_PATH = (
    Path(__file__).resolve().parent / "data" / "atlas_183716_baseline.json"
)


@lru_cache(maxsize=1)
def load_atlas_baseline() -> dict[str, Any]:
    return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))


ATLAS_183716_BASELINE: dict[str, Any] = load_atlas_baseline()


def baseline_metric(*keys: str) -> Any:
    """Return a nested value from the frozen Atlas 183716 baseline."""
    node: Any = load_atlas_baseline()
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"baseline missing key path: {'.'.join(keys)}")
        node = node[key]
    return node
