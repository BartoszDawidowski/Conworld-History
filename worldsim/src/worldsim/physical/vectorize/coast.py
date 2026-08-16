"""Final coastline vectors from ocean mask (Milestone 12)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldsim.physical.terrain.coastline import (
    CoastlineFeature,
    extract_coastline_segments,
    save_coastline_geojson_like,
)
from worldsim.physical.vectorize.coords import polyline_length_norm

__all__ = [
    "CoastlineFeature",
    "build_coastline_vectors",
    "coastline_consistency_score",
    "save_coastline_geojson_like",
    "total_coast_length",
]


def build_coastline_vectors(
    ocean_mask: NDArray[np.bool_],
    water_body_id: NDArray[np.int32] | None = None,
    *,
    max_features: int = 200_000,
) -> list[CoastlineFeature]:
    """Canonical coastline segments retained independently of any hex grid."""
    return extract_coastline_segments(
        np.asarray(ocean_mask, dtype=np.bool_),
        water_body_id,
        max_features=max_features,
    )


def coastline_consistency_score(
    features: list[CoastlineFeature],
    ocean_mask: NDArray[np.bool_],
    *,
    samples: int = 400,
) -> float:
    """Fraction of sampled midpoints that lie on a land/ocean edge."""
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    h, w = ocean.shape
    if not features:
        return 0.0
    rng = np.random.default_rng(1)
    idxs = rng.choice(len(features), size=min(samples, len(features)), replace=False)
    ok = 0
    for fi in idxs:
        geom = features[int(fi)].geometry
        if len(geom) < 2:
            continue
        x = 0.5 * (geom[0][0] + geom[1][0])
        y = 0.5 * (geom[0][1] + geom[1][1])
        i = int(np.floor(x * w)) % w
        j = int(np.floor((1.0 - y) * 0.5 * h))
        j = int(np.clip(j, 0, h - 1))
        o = bool(ocean[j, i])
        neigh = [
            ocean[j, (i + 1) % w],
            ocean[j, (i - 1) % w],
        ]
        if j + 1 < h:
            neigh.append(ocean[j + 1, i])
        if j - 1 >= 0:
            neigh.append(ocean[j - 1, i])
        if any(bool(n) != o for n in neigh):
            ok += 1
    return float(ok / max(len(idxs), 1))


def total_coast_length(features: list[CoastlineFeature]) -> float:
    return float(sum(polyline_length_norm(f.geometry) for f in features))
