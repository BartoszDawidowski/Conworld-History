"""WorldSpatialModel manifest + schema versioning (Milestone 16)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from worldsim import SCHEMA_VERSION

# Independent of seed SCHEMA_VERSION — bumping this does not reshuffle module seeds.
# v2: PR-1 hex layout algorithm v2 + length-units migration metadata.
WORLD_MODEL_SCHEMA_VERSION = 2


@dataclass
class WorldManifest:
    """Top-level world dataset manifest (§39)."""

    world_model_schema_version: int = WORLD_MODEL_SCHEMA_VERSION
    seed_schema_version: int = SCHEMA_VERSION
    master_seed: int | None = None
    stage: str = "world"
    paths: dict[str, str] = field(
        default_factory=lambda: {
            "config": "config.json",
            "rasters": "physical/rasters",
            "vectors": "physical/vectors",
            "analysis_grid": "physical/analysis_grid",
            "environment_timeline": "timeline/environment",
        }
    )
    resolutions: dict[str, list[int]] = field(default_factory=dict)
    hex_n_cells: int | None = None
    acceptance_ok: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> WorldManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        version = int(data.get("world_model_schema_version", 0))
        if version != WORLD_MODEL_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported world_model_schema_version {version}; "
                f"expected {WORLD_MODEL_SCHEMA_VERSION}"
            )
        return cls(
            world_model_schema_version=version,
            seed_schema_version=int(data.get("seed_schema_version", SCHEMA_VERSION)),
            master_seed=data.get("master_seed"),
            stage=str(data.get("stage", "world")),
            paths=dict(data.get("paths", {})),
            resolutions={
                k: list(v) for k, v in dict(data.get("resolutions", {})).items()
            },
            hex_n_cells=data.get("hex_n_cells"),
            acceptance_ok=data.get("acceptance_ok"),
            extra=dict(data.get("extra", {})),
        )
