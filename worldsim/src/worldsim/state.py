"""Master physical world state container (architecture §15)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from worldsim.config import PlanetConfig
from worldsim.seeds import SeedManifest
from worldsim.spatial.coordinates import CoordinateSystem
from worldsim.spatial.extent import SpatialExtent


@dataclass
class PhysicalWorldState:
    """In-memory generation state. No hidden global module state."""

    config: PlanetConfig
    seeds: SeedManifest
    coordinates: CoordinateSystem = field(default_factory=CoordinateSystem)
    extents: dict[str, SpatialExtent] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Stage payloads are attached by later milestones.
    tectonics: Any = None
    terrain: Any = None
    ocean: Any = None
    climate: Any = None
    atmosphere: Any = None
    moisture: Any = None
    erosion: Any = None
    hydrology: Any = None
    ecology: Any = None
    rasters: dict[str, Any] = field(default_factory=dict)
    vectors: dict[str, Any] = field(default_factory=dict)
    analysis_grid: Any = None
