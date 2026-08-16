"""Plan B6 — Douglas–Peucker simplify + Chaikin smooth for open polylines.

Presentation/export only. Preserves endpoints; splits at cylindrical dateline
seams (|Δx| > 0.5 in normalised coords) so smoothing never invents wrap chords.
"""

from __future__ import annotations

from typing import Sequence

Point = tuple[float, float]

_MAX_DX = 0.5


def _dist2(a: Point, b: Point) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _perp_dist2(p: Point, a: Point, b: Point) -> float:
    """Squared distance from p to segment ab (planar)."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx = bx - ax
    dy = by - ay
    if dx == 0.0 and dy == 0.0:
        return _dist2(p, a)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return _dist2(p, (ax + t * dx, ay + t * dy))


def douglas_peucker(points: Sequence[Point], epsilon: float) -> list[Point]:
    """Open-polyline Ramer–Douglas–Peucker. Keeps endpoints."""
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) <= 2 or epsilon <= 0.0:
        return pts
    eps2 = float(epsilon) * float(epsilon)

    def _rec(start: int, end: int) -> list[int]:
        if end <= start + 1:
            return [start, end]
        a = pts[start]
        b = pts[end]
        max_d = -1.0
        idx = start
        for i in range(start + 1, end):
            d = _perp_dist2(pts[i], a, b)
            if d > max_d:
                max_d = d
                idx = i
        if max_d <= eps2:
            return [start, end]
        left = _rec(start, idx)
        right = _rec(idx, end)
        return left[:-1] + right

    keep = _rec(0, len(pts) - 1)
    return [pts[i] for i in keep]


def chaikin_open(points: Sequence[Point], iterations: int = 2) -> list[Point]:
    """Chaikin corner-cutting for open polylines (keeps endpoints)."""
    pts = [(float(x), float(y)) for x, y in points]
    iters = max(0, int(iterations))
    if len(pts) < 2 or iters == 0:
        return pts
    for _ in range(iters):
        if len(pts) < 2:
            break
        nxt: list[Point] = [pts[0]]
        for i in range(len(pts) - 1):
            p0 = pts[i]
            p1 = pts[i + 1]
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            nxt.append(q)
            nxt.append(r)
        nxt.append(pts[-1])
        pts = nxt
    return pts


def split_seam_safe(
    points: Sequence[Point], *, max_dx: float = _MAX_DX
) -> list[list[Point]]:
    """Split open polyline wherever consecutive |Δx| exceeds ``max_dx``."""
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 2:
        return [pts] if pts else []
    pieces: list[list[Point]] = []
    cur: list[Point] = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - cur[-1][0]) > max_dx:
            if len(cur) >= 2:
                pieces.append(cur)
            cur = [p]
        else:
            cur.append(p)
    if len(cur) >= 2:
        pieces.append(cur)
    return pieces


def smooth_open_polyline(
    points: Sequence[Point],
    *,
    simplify_eps: float = 0.0012,
    chaikin_iters: int = 2,
    max_dx: float = _MAX_DX,
) -> list[list[Point]]:
    """Simplify + Chaikin per seam-safe piece. Returns one or more open polylines."""
    out: list[list[Point]] = []
    for piece in split_seam_safe(points, max_dx=max_dx):
        if len(piece) < 2:
            continue
        simplified = douglas_peucker(piece, simplify_eps)
        if len(simplified) < 2:
            continue
        smoothed = chaikin_open(simplified, chaikin_iters)
        # Chaikin can reintroduce tiny seam crossings near dateline — re-split.
        for sub in split_seam_safe(smoothed, max_dx=max_dx):
            if len(sub) >= 2:
                out.append(sub)
    return out


def vertex_count(polylines: Sequence[Sequence[Point]]) -> int:
    return int(sum(len(p) for p in polylines))


def _chaikin_closed(points: Sequence[Point], iterations: int = 2) -> list[Point]:
    pts = [(float(x), float(y)) for x, y in points]
    iters = max(0, int(iterations))
    if len(pts) < 3 or iters == 0:
        return pts
    for _ in range(iters):
        n = len(pts)
        nxt: list[Point] = []
        for i in range(n):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]
            nxt.append((0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]))
            nxt.append((0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]))
        pts = nxt
    return pts


def _laplacian_closed(
    points: Sequence[Point], iterations: int = 4, weight: float = 0.5
) -> list[Point]:
    pts = [(float(x), float(y)) for x, y in points]
    w = min(1.0, max(0.0, float(weight)))
    for _ in range(max(0, int(iterations))):
        n = len(pts)
        if n < 3:
            break
        nxt: list[Point] = []
        for i in range(n):
            prev = pts[(i - 1) % n]
            mid = pts[i]
            nxtp = pts[(i + 1) % n]
            nxt.append(
                (
                    (1.0 - w) * mid[0] + 0.5 * w * (prev[0] + nxtp[0]),
                    (1.0 - w) * mid[1] + 0.5 * w * (prev[1] + nxtp[1]),
                )
            )
        pts = nxt
    return pts


def smooth_closed_ring(
    points: Sequence[Point],
    *,
    simplify_eps: float = 0.0015,
    laplacian_iters: int = 2,
    chaikin_iters: int = 1,
) -> list[Point]:
    """Mild presentation smooth for lake rings. Falls back if area collapses.

    Aggressive DP/Laplacian produced self-intersections → Godot triangulation
    failures and missing large lakes.
    """
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) >= 2 and _dist2(pts[0], pts[-1]) < 1e-12:
        pts = pts[:-1]
    if len(pts) < 3:
        return [(float(x), float(y)) for x, y in points]

    def _area(poly: Sequence[Point]) -> float:
        n = len(poly)
        if n < 3:
            return 0.0
        a = 0.0
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            a += x0 * y1 - x1 * y0
        return abs(a) * 0.5

    area0 = _area(pts)
    # Skip heavy DP on lakes — only light Laplacian + one Chaikin.
    smoothed = _laplacian_closed(pts, laplacian_iters, 0.28)
    smoothed = _chaikin_closed(smoothed, chaikin_iters)
    if not smoothed or len(smoothed) < 3:
        out = pts
    else:
        area1 = _area(smoothed)
        if area0 > 1e-12 and (area1 < 0.55 * area0 or area1 > 1.6 * area0):
            out = pts
        else:
            out = smoothed
    if _dist2(out[0], out[-1]) >= 1e-12:
        out = list(out) + [out[0]]
    return out
