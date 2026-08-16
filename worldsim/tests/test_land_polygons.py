"""Plan B3 — land polygon extraction from ocean mask."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from worldsim.physical.vectorize.land import (
    extract_land_polygons,
    land_coverage_score,
    land_polygons_to_geojson,
)


def test_simple_island_polygon() -> None:
    ocean = np.ones((32, 64), dtype=bool)
    ocean[10:20, 20:40] = False  # land rectangle
    polys = extract_land_polygons(ocean, min_cells=4)
    assert len(polys) >= 1
    assert all(len(p.ring) >= 4 for p in polys)
    assert all(p.ring[0] == p.ring[-1] for p in polys)
    score = land_coverage_score(polys, ocean)
    assert score >= 0.85
    from worldsim.physical.vectorize.land import land_cell_recall

    assert land_cell_recall(polys, ocean) >= 0.95


def test_two_islands() -> None:
    ocean = np.ones((40, 80), dtype=bool)
    ocean[5:12, 5:15] = False
    ocean[25:35, 50:70] = False
    polys = extract_land_polygons(ocean, min_cells=4)
    comps = {p.component_id for p in polys}
    assert len(comps) >= 2


def test_no_dateline_chord() -> None:
    ocean = np.ones((24, 48), dtype=bool)
    ocean[8:16, :] = False  # land belt wrapping E–W
    ocean[8:16, 20:28] = True  # cut a sea gap so not one full wrap fill
    polys = extract_land_polygons(ocean, min_cells=4)
    for p in polys:
        ring = p.ring
        for (x0, _y0), (x1, _y1) in zip(ring, ring[1:]):
            assert abs(x1 - x0) <= 0.5 + 1e-9


def test_inland_sea_hole_not_exported_as_land() -> None:
    ocean = np.ones((40, 80), dtype=bool)
    ocean[5:35, 10:70] = False  # continent
    ocean[15:25, 30:50] = True  # inland sea (hole)
    polys = extract_land_polygons(ocean, min_cells=4)
    assert len(polys) >= 1
    # Hole ring alone would be small; we only assert no exported ring is an ocean pocket.
    h, w = ocean.shape
    land = ~ocean.astype(bool)
    for p in polys:
        pts = p.ring[:-1]
        # Edge-mid inward samples should be majority-land (same rule as filter).
        step = max(0.5 / w, 1.0 / h)
        land_v = ocean_v = 0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
            dx, dy = x1 - x0, y1 - y0
            L = float(np.hypot(dx, dy)) or 1e-9
            nx, ny = (-dy / L) * step, (dx / L) * step
            from worldsim.physical.vectorize.land import _point_in_ring

            for sx, sy in ((mx + nx, my + ny), (mx - nx, my - ny)):
                if not _point_in_ring(sx, sy, p.ring):
                    continue
                c = int(np.clip(np.floor(sx * w), 0, w - 1))
                r = int(np.clip(np.floor((1.0 - sy) * 0.5 * h), 0, h - 1))
                if land[r, c]:
                    land_v += 1
                else:
                    ocean_v += 1
        assert land_v >= ocean_v


def test_geojson_roundtrip(tmp_path: Path) -> None:
    ocean = np.ones((16, 32), dtype=bool)
    ocean[4:12, 8:24] = False
    polys = extract_land_polygons(ocean)
    geo = land_polygons_to_geojson(polys)
    path = tmp_path / "land.geojson"
    path.write_text(json.dumps(geo) + "\n", encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["type"] == "FeatureCollection"
    assert len(loaded["features"]) == len(polys)
    assert loaded["features"][0]["geometry"]["type"] == "Polygon"
