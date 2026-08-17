"""Physical grid metrics for cylindrical equal-area rasters (PR-1).

Cell counts are not physical lengths. ``GridMetrics`` converts between the
project ``(x, y)`` plane (``y = sin(lat)``) and kilometres on the sphere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from numpy.typing import NDArray


# Mean Earth radius (km). Overridable via planet.radius_km.
EARTH_RADIUS_KM = 6371.0

# PyFlwDir-style D8 bit codes → (dj, di) with j north→south, i west→east.
_D8_OFFSETS: dict[int, tuple[int, int]] = {
    1: (0, 1),  # E
    2: (1, 1),  # SE
    4: (1, 0),  # S
    8: (1, -1),  # SW
    16: (0, -1),  # W
    32: (-1, -1),  # NW
    64: (-1, 0),  # N
    128: (-1, 1),  # NE
}


@dataclass(frozen=True)
class GridMetrics:
    """Metric helpers for one raster shape on the cylindrical equal-area plane."""

    width: int
    height: int
    radius_km: float = EARTH_RADIUS_KM
    wrap_x: bool = True
    wrap_y: bool = False
    projection: str = "cylindrical_equal_area"

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.radius_km <= 0.0:
            raise ValueError("radius_km must be positive")
        if self.wrap_y:
            raise ValueError("wrap_y must be false")
        if not self.wrap_x:
            raise ValueError("wrap_x must be true for the cylindrical world")
        if self.projection != "cylindrical_equal_area":
            raise ValueError(
                f"unsupported projection {self.projection!r}; "
                "expected cylindrical_equal_area"
            )

    @property
    def circumference_km(self) -> float:
        return 2.0 * math.pi * float(self.radius_km)

    @property
    def cell_area_km2(self) -> float:
        """Equal-area cells share surface area."""
        sphere = 4.0 * math.pi * float(self.radius_km) ** 2
        return sphere / float(self.width * self.height)

    def cells_for_area_km2(self, area_km2: float) -> int:
        """Minimum cell count whose equal-area coverage is ≥ ``area_km2``."""
        return max(1, int(math.ceil(float(area_km2) / max(self.cell_area_km2, 1e-12))))

    def row_y_centers(self) -> NDArray[np.float64]:
        """Normalised ``y`` at cell centres; ``j=0`` is north."""
        j = np.arange(self.height, dtype=np.float64)
        return 1.0 - (j + 0.5) * 2.0 / float(self.height)

    def row_latitude_rad(self) -> NDArray[np.float64]:
        y = self.row_y_centers()
        # Clamp for numerical safety near poles (centres never reach ±1 on raster).
        y = np.clip(y, -1.0 + 1e-12, 1.0 - 1e-12)
        return np.arcsin(y)

    def row_latitude_deg(self) -> NDArray[np.float64]:
        return np.degrees(self.row_latitude_rad())

    def ew_spacing_km(self) -> NDArray[np.float64]:
        """East–west centre spacing (km) per row."""
        lat = self.row_latitude_rad()
        return self.circumference_km * np.cos(lat) / float(self.width)

    def ns_spacing_km(self) -> NDArray[np.float64]:
        """North–south centre spacing (km) between row ``j`` and ``j+1``.

        Length ``height``; last entry repeats the previous gap (edge).
        """
        y = self.row_y_centers()
        lat = np.arcsin(np.clip(y, -1.0 + 1e-12, 1.0 - 1e-12))
        dphi = np.abs(np.diff(lat))
        ds = float(self.radius_km) * dphi
        if ds.size == 0:
            return np.zeros(self.height, dtype=np.float64)
        out = np.empty(self.height, dtype=np.float64)
        out[:-1] = ds
        out[-1] = ds[-1]
        return out

    def cells_from_km_ew(self, distance_km: float, row: int) -> float:
        """Convert km to EW cell count at ``row`` (diagnostic / library bridge)."""
        spacing = float(self.ew_spacing_km()[int(row)])
        if spacing <= 1e-12:
            return float("inf")
        return float(distance_km) / spacing

    def cells_from_km_ns(self, distance_km: float, row: int) -> float:
        spacing = float(self.ns_spacing_km()[int(row)])
        if spacing <= 1e-12:
            return float("inf")
        return float(distance_km) / spacing

    def km_from_cells_ew(self, cells: float, *, row: int | None = None) -> float:
        """Convert EW cell count to km (mid-latitude row if ``row`` omitted)."""
        j = int(self.height // 2) if row is None else int(row)
        return float(cells) * float(self.ew_spacing_km()[j])

    def km_from_cells_ns(self, cells: float, *, row: int | None = None) -> float:
        j = int(self.height // 2) if row is None else int(row)
        return float(cells) * float(self.ns_spacing_km()[j])

    def km_from_cells_isotropic_midlat(self, cells: float) -> float:
        """Atlas-era cell knobs → km using mid-latitude EW spacing."""
        return self.km_from_cells_ew(cells, row=self.height // 2)

    def metric_gradients(
        self, field: NDArray[np.floating]
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """``(d_field/d_east_m, d_field/d_south_m)`` with E–W wrap; no N–S wrap."""
        arr = np.asarray(field, dtype=np.float64)
        if arr.shape != (self.height, self.width):
            raise ValueError(
                f"field shape {arr.shape} != grid {(self.height, self.width)}"
            )
        ew = self.ew_spacing_km() * 1000.0  # metres
        ns = self.ns_spacing_km() * 1000.0

        de_di = 0.5 * (np.roll(arr, -1, axis=1) - np.roll(arr, 1, axis=1))
        d_east = de_di / ew[:, None]

        d_south = np.empty_like(arr)
        for j in range(self.height):
            if j == 0:
                d_south[j] = (arr[j + 1] - arr[j]) / ns[j]
            elif j == self.height - 1:
                d_south[j] = (arr[j] - arr[j - 1]) / ns[j - 1]
            else:
                # Centre of row j-1 → centre of j+1 spans ns[j-1] + ns[j].
                step = float(ns[j - 1] + ns[j])
                d_south[j] = (arr[j + 1] - arr[j - 1]) / max(step, 1e-12)
        return d_east, d_south

    def metric_slope(self, elevation_m: NDArray[np.floating]) -> NDArray[np.float64]:
        gx, gy = self.metric_gradients(elevation_m)
        return np.hypot(gx, gy)

    def d8_step_length_m(self, row: int, d8_code: int) -> float:
        """Physical length (m) of one D8 step leaving ``row``."""
        return self.d8_step_length_km(row, d8_code) * 1000.0

    def d8_step_length_km(self, row: int, d8_code: int) -> float:
        """Physical length (km) of one D8 step leaving ``row``."""
        code = int(d8_code)
        if code not in _D8_OFFSETS:
            return 0.0
        dj, di = _D8_OFFSETS[code]
        j = int(row)
        ew = float(self.ew_spacing_km()[j])
        if dj == 0:
            return abs(di) * ew
        if dj > 0:
            ns = float(self.ns_spacing_km()[j])
        else:
            ns = float(self.ns_spacing_km()[max(j - 1, 0)])
        if di == 0:
            return abs(dj) * ns
        return math.hypot(ew, ns)

    def d8_step_length_km_field(
        self, flow_direction: NDArray[np.integer]
    ) -> NDArray[np.float64]:
        """Per-cell D8 step length (km) from a flow-direction raster."""
        d8 = np.asarray(flow_direction)
        if d8.shape != (self.height, self.width):
            raise ValueError("flow_direction shape mismatch")
        out = np.zeros((self.height, self.width), dtype=np.float64)
        ew = self.ew_spacing_km()
        ns = self.ns_spacing_km()
        ns_north = np.empty(self.height, dtype=np.float64)
        ns_north[0] = ns[0]
        ns_north[1:] = ns[:-1]
        row_idx = np.broadcast_to(
            np.arange(self.height, dtype=np.int32)[:, None], d8.shape
        )
        for code, (dj, di) in _D8_OFFSETS.items():
            sel = d8 == code
            if not np.any(sel):
                continue
            if dj == 0:
                length = np.abs(float(di)) * ew
            elif di == 0:
                gap = ns if dj > 0 else ns_north
                length = np.abs(float(dj)) * gap
            else:
                gap = ns if dj > 0 else ns_north
                length = np.hypot(ew, gap)
            out[sel] = length[row_idx[sel]]
        return out

    def neighbourhood_halfwidth_cells(self, radius_km: float) -> NDArray[np.int32]:
        """Per-row EW half-width in cells for a circular-ish km radius."""
        ew = self.ew_spacing_km()
        out = np.empty(self.height, dtype=np.int32)
        for j in range(self.height):
            spacing = float(ew[j])
            if spacing <= 1e-12:
                out[j] = self.width // 2
            else:
                out[j] = int(math.ceil(float(radius_km) / spacing))
        return out

    def distance_to_mask_km(
        self,
        mask: NDArray[np.bool_],
        *,
        connectivity: int = 4,
    ) -> NDArray[np.float64]:
        """Shortest-path distance (km) to nearest True cell; E–W wrap, no N–S wrap."""
        import heapq

        m = np.asarray(mask, dtype=bool)
        if m.shape != (self.height, self.width):
            raise ValueError("mask shape mismatch")
        dist = np.full(m.shape, np.inf, dtype=np.float64)
        heap: list[tuple[float, int, int]] = []
        js, is_ = np.where(m)
        for j, i in zip(js.tolist(), is_.tolist(), strict=False):
            dist[j, i] = 0.0
            heapq.heappush(heap, (0.0, int(j), int(i)))

        if connectivity == 8:
            deltas = (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
                (-1, -1),
                (-1, 1),
                (1, -1),
                (1, 1),
            )
        else:
            deltas = ((-1, 0), (1, 0), (0, -1), (0, 1))

        ew = self.ew_spacing_km()
        ns = self.ns_spacing_km()
        while heap:
            base, j, i = heapq.heappop(heap)
            if base > float(dist[j, i]) + 1e-12:
                continue
            for dj, di in deltas:
                nj = j + dj
                if nj < 0 or nj >= self.height:
                    continue
                ni = (i + di) % self.width
                if dj == 0:
                    step = abs(di) * float(ew[j])
                elif di == 0:
                    step = abs(dj) * float(ns[j if dj > 0 else max(j - 1, 0)])
                else:
                    step = math.hypot(
                        float(ew[j]),
                        float(ns[j if dj > 0 else max(j - 1, 0)]),
                    )
                cand = base + step
                if cand + 1e-12 < dist[nj, ni]:
                    dist[nj, ni] = cand
                    heapq.heappush(heap, (cand, nj, ni))
        return dist

    def to_diagnostics(self) -> dict[str, Any]:
        ew = self.ew_spacing_km()
        ns = self.ns_spacing_km()
        mid = self.height // 2
        return {
            "width": self.width,
            "height": self.height,
            "radius_km": float(self.radius_km),
            "projection": self.projection,
            "cell_area_km2": float(self.cell_area_km2),
            "ew_spacing_km_equator": float(ew[mid]),
            "ew_spacing_km_row0": float(ew[0]),
            "ns_spacing_km_mid": float(ns[mid]),
            "mean_latitude_deg": float(np.mean(self.row_latitude_deg())),
        }


@lru_cache(maxsize=32)
def grid_metrics(
    width: int,
    height: int,
    *,
    radius_km: float = EARTH_RADIUS_KM,
) -> GridMetrics:
    """Cached factory (shape + radius)."""
    return GridMetrics(width=int(width), height=int(height), radius_km=float(radius_km))
