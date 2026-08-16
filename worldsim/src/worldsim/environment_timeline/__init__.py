"""Environment timeline scaffold (architecture §37 / Milestone 19).

Baseline climatology + sparse anomalies. No full palaeoclimate engine.
"""

from __future__ import annotations

from worldsim.environment_timeline.baseline import BaselineEnvironmentSnapshot
from worldsim.environment_timeline.schema import (
    ENVIRONMENT_TIMELINE_SCHEMA_VERSION,
    EnvironmentalAnomaly,
    EnvironmentModifiers,
    SpatialScope,
    aggregate_modifiers,
)
from worldsim.environment_timeline.timeline import (
    EnvironmentTimeline,
    EnvironmentTimelineProtocol,
    build_environment_timeline,
)

__all__ = [
    "ENVIRONMENT_TIMELINE_SCHEMA_VERSION",
    "BaselineEnvironmentSnapshot",
    "EnvironmentModifiers",
    "EnvironmentTimeline",
    "EnvironmentTimelineProtocol",
    "EnvironmentalAnomaly",
    "SpatialScope",
    "aggregate_modifiers",
    "build_environment_timeline",
]
