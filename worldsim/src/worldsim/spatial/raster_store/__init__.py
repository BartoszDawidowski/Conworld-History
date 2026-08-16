"""Canonical raster layer store for WorldSpatialModel (Milestone 16)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass
class RasterStore:
    """Named NumPy layers with optional extent metadata.

    Large numeric data lives in ``.npz`` files — never JSON.
    """

    layers: dict[str, NDArray[Any]] = field(default_factory=dict)
    extents: dict[str, dict[str, int]] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    def put(
        self,
        name: str,
        array: NDArray[Any],
        *,
        extent_key: str | None = None,
        note: str = "",
    ) -> None:
        arr = np.asarray(array)
        self.layers[name] = arr
        if extent_key is not None and arr.ndim >= 2:
            self.extents[extent_key] = {
                "height": int(arr.shape[-2]),
                "width": int(arr.shape[-1]),
            }
        if note:
            self.notes[name] = note

    def get(self, name: str) -> NDArray[Any]:
        if name not in self.layers:
            raise KeyError(f"raster layer {name!r} not found")
        return self.layers[name]

    def has(self, name: str) -> bool:
        return name in self.layers

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        # Group by first path segment of name: terrain/elevation → terrain.npz key elevation
        groups: dict[str, dict[str, NDArray[Any]]] = {}
        for name, arr in self.layers.items():
            if "/" in name:
                group, key = name.split("/", 1)
            else:
                group, key = "misc", name
            groups.setdefault(group, {})[key] = arr
        catalog: dict[str, Any] = {
            "layers": sorted(self.layers.keys()),
            "extents": self.extents,
            "notes": self.notes,
            "files": {},
        }
        for group, arrays in sorted(groups.items()):
            path = directory / f"{group}.npz"
            np.savez_compressed(path, **arrays)
            catalog["files"][group] = path.name
        (directory / "layers.json").write_text(
            json.dumps(catalog, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> RasterStore:
        catalog_path = directory / "layers.json"
        if not catalog_path.is_file():
            raise FileNotFoundError(f"missing raster catalog: {catalog_path}")
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        store = cls(
            extents=dict(catalog.get("extents", {})),
            notes=dict(catalog.get("notes", {})),
        )
        files = catalog.get("files", {})
        for group, filename in files.items():
            data = np.load(directory / filename)
            for key in data.files:
                name = f"{group}/{key}" if group != "misc" else key
                store.layers[name] = data[key]
        return store
