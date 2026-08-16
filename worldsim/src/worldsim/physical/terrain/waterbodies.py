"""Connected water-body labelling under cylindrical topology."""

from __future__ import annotations

from collections import deque

import numpy as np
from numpy.typing import NDArray


def label_water_bodies(
    ocean_mask: NDArray[np.bool_],
) -> tuple[NDArray[np.int32], int]:
    """4-connected labels with E–W wrap; no N–S wrap.

    Returns ``(water_body_id, count)`` where land is 0 and water ids start at 1.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    height, width = ocean.shape
    labels = np.zeros((height, width), dtype=np.int32)
    current = 0

    for j in range(height):
        for i in range(width):
            if not ocean[j, i] or labels[j, i] != 0:
                continue
            current += 1
            queue: deque[tuple[int, int]] = deque([(i, j)])
            labels[j, i] = current
            while queue:
                x, y = queue.popleft()
                for nx, ny in (
                    ((x + 1) % width, y),
                    ((x - 1) % width, y),
                    (x, y + 1),
                    (x, y - 1),
                ):
                    if ny < 0 or ny >= height:
                        continue
                    if ocean[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = current
                        queue.append((nx, ny))
    return labels, current


def largest_water_body_id(water_body_id: NDArray[np.int32]) -> int:
    ids, counts = np.unique(water_body_id[water_body_id > 0], return_counts=True)
    if len(ids) == 0:
        return 0
    return int(ids[int(np.argmax(counts))])


def ocean_basin_ids(
    water_body_id: NDArray[np.int32],
    *,
    min_fraction: float = 0.02,
) -> NDArray[np.int32]:
    """Mark sizable water bodies as ocean basins; tiny lakes keep body id only.

    For Milestone 5, basins mirror water-body ids that exceed ``min_fraction``
    of the map area; smaller bodies get basin id 0.
    """
    height, width = water_body_id.shape
    area = height * width
    out = np.zeros_like(water_body_id)
    for wid in np.unique(water_body_id):
        if wid <= 0:
            continue
        mask = water_body_id == wid
        if float(mask.mean()) >= min_fraction:
            out[mask] = wid
    return out
