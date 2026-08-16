"""Coastline vectorization with merge + seam-safe polylines (Milestone A5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

_MAX_DX = 0.5


@dataclass
class CoastlineFeature:
    id: int
    geometry: list[tuple[float, float]]  # normalised (x, y) vertices
    water_body_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "water_body_id": self.water_body_id,
            "geometry": [[float(x), float(y)] for x, y in self.geometry],
        }


def _clamp_x(x: float) -> float:
    if x >= 1.0:
        return float(np.nextafter(1.0, 0.0))
    if x < 0.0:
        return 0.0
    return float(x)


def _xy(i: float, j: float, width: int, height: int) -> tuple[float, float]:
    """Continuous grid → normalised; x kept in [0,1) without wrapping 1→0 mid-edge."""
    x = _clamp_x((float(i) + 0.5) / float(width))
    y = 1.0 - (float(j) + 0.5) * 2.0 / float(height)
    return x, float(y)


def _crosses_seam(p0: tuple[float, float], p1: tuple[float, float]) -> bool:
    return abs(p1[0] - p0[0]) > _MAX_DX


def count_micro_edges(ocean_mask: NDArray[np.bool_]) -> int:
    """Count land/ocean 4-neighbour boundary edges (pre-merge cardinality)."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    h, w = ocean.shape
    n = 0
    # horizontal
    n += int(np.count_nonzero(ocean[:-1, :] != ocean[1:, :]))
    # vertical with wrap
    n += int(np.count_nonzero(ocean[:, :] != ocean[:, np.roll(np.arange(w), -1)]))
    return n


def extract_coastline_segments(
    ocean_mask: NDArray[np.bool_],
    water_body_id: NDArray[np.int32] | None = None,
    *,
    max_features: int = 200_000,
) -> list[CoastlineFeature]:
    """Extract merged coastline polylines (E–W seam-safe).

    Horizontal land/ocean edges are run-length merged along each row interface;
    vertical edges (incl. dateline column) are merged along each column.
    No segment is emitted whose normalised ``|Δx| > 0.5`` (no full-width chords).
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    height, width = ocean.shape
    if water_body_id is None:
        wb = ocean.astype(np.int32)
    else:
        wb = np.asarray(water_body_id, dtype=np.int32)

    pieces: list[tuple[list[tuple[float, float]], int]] = []

    # --- Horizontal interfaces between row j and j+1 ---
    for j in range(height - 1):
        i = 0
        while i < width:
            a = bool(ocean[j, i])
            b = bool(ocean[j + 1, i])
            if a == b:
                i += 1
                continue
            wid = int(wb[j, i] if a else wb[j + 1, i])
            i0 = i
            i += 1
            while i < width:
                a2 = bool(ocean[j, i])
                b2 = bool(ocean[j + 1, i])
                if a2 == b2:
                    break
                wid2 = int(wb[j, i] if a2 else wb[j + 1, i])
                if wid2 != wid:
                    break
                i += 1
            # Run of columns [i0, i) along horizontal interface at j+0.5
            p0 = _xy(i0 - 0.5, j + 0.5, width, height)
            p1 = _xy(i - 0.5, j + 0.5, width, height)
            if not _crosses_seam(p0, p1):
                pieces.append(([p0, p1], wid))

    # --- Vertical interfaces between col i and i+1 (wrap) ---
    for i in range(width):
        ni = (i + 1) % width
        j = 0
        while j < height:
            a = bool(ocean[j, i])
            b = bool(ocean[j, ni])
            if a == b:
                j += 1
                continue
            wid = int(wb[j, i] if a else wb[j, ni])
            j0 = j
            j += 1
            while j < height:
                a2 = bool(ocean[j, i])
                b2 = bool(ocean[j, ni])
                if a2 == b2:
                    break
                wid2 = int(wb[j, i] if a2 else wb[j, ni])
                if wid2 != wid:
                    break
                j += 1
            # Vertical run along x = i+0.5 from row j0 to j
            p0 = _xy(i + 0.5, j0 - 0.5, width, height)
            p1 = _xy(i + 0.5, j - 0.5, width, height)
            if not _crosses_seam(p0, p1):
                pieces.append(([p0, p1], wid))

    if len(pieces) > max_features:
        pieces.sort(
            key=lambda pw: abs(pw[0][1][0] - pw[0][0][0]) + abs(pw[0][1][1] - pw[0][0][1]),
            reverse=True,
        )
        pieces = pieces[:max_features]

    return [
        CoastlineFeature(id=k + 1, geometry=pts, water_body_id=wid)
        for k, (pts, wid) in enumerate(pieces)
    ]


def save_coastline_geojson_like(
    features: list[CoastlineFeature],
    path: Path,
) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": f.id,
                    "water_body_id": f.water_body_id,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": f.geometry,
                },
            }
            for f in features
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
