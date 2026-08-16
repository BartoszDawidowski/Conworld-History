"""Deterministic named seed derivation from a master seed."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from worldsim import SCHEMA_VERSION

# Named modules from architecture §16. Order is documentary only; derivation
# does not depend on consumption order.
DEFAULT_MODULE_NAMES: tuple[str, ...] = (
    "tectonics",
    "terrain_detail",
    "ocean",
    "climate",
    "erosion_1",
    "hydrology",
    "erosion_2",
    "vectorization",
    "ecology",
    "environment_timeline",
)


def derive_seed(
    master_seed: int,
    module_name: str,
    schema_version: int = SCHEMA_VERSION,
) -> int:
    """Return a stable uint64-range seed for ``module_name``.

    Uses ``hash(master_seed, module_name, schema_version)`` via SHA-256 so that
    adding an unrelated module does not reshuffle existing named seeds.
    """
    if not module_name:
        raise ValueError("module_name must be non-empty")
    payload = f"{int(master_seed)}\0{module_name}\0{int(schema_version)}".encode(
        "utf-8"
    )
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


@dataclass(frozen=True)
class SeedManifest:
    """Serializable deterministic seed table for one generation run."""

    master_seed: int
    schema_version: int
    modules: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "master_seed": self.master_seed,
            "schema_version": self.schema_version,
            "modules": dict(self.modules),
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def build_seed_manifest(
    master_seed: int,
    *,
    schema_version: int = SCHEMA_VERSION,
    module_names: Iterable[str] = DEFAULT_MODULE_NAMES,
) -> SeedManifest:
    modules = {
        name: derive_seed(master_seed, name, schema_version) for name in module_names
    }
    return SeedManifest(
        master_seed=int(master_seed),
        schema_version=int(schema_version),
        modules=modules,
    )
