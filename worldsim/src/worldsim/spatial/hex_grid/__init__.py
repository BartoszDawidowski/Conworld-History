"""Analytical 256×128 flat-top hex grid (Milestone 15 / Stage O)."""

from __future__ import annotations

from worldsim.spatial.hex_grid.layout import (
    HexGridSpec,
    hex_corner_offsets,
    hex_id,
    hex_vertices_xy,
    neighbours,
)
from worldsim.spatial.hex_grid.pipeline import HexAnalysisResult, build_hex_analysis_grid

__all__ = [
    "HexAnalysisResult",
    "HexGridSpec",
    "build_hex_analysis_grid",
    "hex_corner_offsets",
    "hex_id",
    "hex_vertices_xy",
    "neighbours",
]
