"""Analytical 256×128 flat-top hex grid (Milestone 15 / Stage O)."""

from __future__ import annotations

from worldsim.spatial.hex_grid.layout import (
    HEX_LAYOUT_ALGORITHM_VERSION,
    HexGridSpec,
    hex_corner_offsets,
    hex_id,
    hex_vertices_xy,
    neighbours,
)
from worldsim.spatial.hex_grid.pipeline import HexAnalysisResult, build_hex_analysis_grid

__all__ = [
    "HEX_LAYOUT_ALGORITHM_VERSION",
    "HexAnalysisResult",
    "HexGridSpec",
    "build_hex_analysis_grid",
    "hex_corner_offsets",
    "hex_id",
    "hex_vertices_xy",
    "neighbours",
]
