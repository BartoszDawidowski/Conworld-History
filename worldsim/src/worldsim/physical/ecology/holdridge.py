"""Holdridge life-zone classification (Milestone 14 / Stage N)."""

from __future__ import annotations

from enum import IntEnum

import numpy as np
from numpy.typing import NDArray


class HoldridgeOverride(IntEnum):
    OCEAN = 0
    LAKE = 1
    ICE = 2
    ALPINE_BARE = 3
    # Life zones start at 10+


# Latitudinal belts by biotemperature (°C) — Holdridge-like power-of-two edges
_BIO_EDGES = (1.5, 3.0, 6.0, 12.0, 24.0)
_BIO_NAMES = (
    "polar",
    "subpolar",
    "boreal",
    "cool_temperate",
    "warm_temperate",
    "tropical",
)

# Humidity provinces by PET ratio (wet → dry)
_PET_EDGES = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
_HUM_NAMES = (
    "superhumid",
    "perhumid",
    "humid",
    "subhumid",
    "semiarid",
    "arid",
    "perarid",
)

# Wikipedia / IIASA-style physiognomic names (bio × humidity).
# Full Cartesian product is 42 cells; classic maps list ~38 *realisable* zones —
# extras are rare/edge combos we still label for completeness.
_LIFE_ZONE_DISPLAY: tuple[tuple[str, ...], ...] = (
    # polar
    (
        "Polar rain tundra",
        "Polar wet tundra",
        "Polar moist tundra",
        "Polar dry tundra",
        "Polar desert",
        "Polar desert",
        "Polar desert",
    ),
    # subpolar
    (
        "Subpolar rain tundra",
        "Subpolar wet tundra",
        "Subpolar moist tundra",
        "Subpolar dry tundra",
        "Subpolar desert",
        "Subpolar desert",
        "Subpolar desert",
    ),
    # boreal
    (
        "Boreal rain forest",
        "Boreal wet forest",
        "Boreal moist forest",
        "Boreal dry scrub",
        "Boreal desert",
        "Boreal desert",
        "Boreal desert",
    ),
    # cool temperate
    (
        "Cool temperate rain forest",
        "Cool temperate wet forest",
        "Cool temperate moist forest",
        "Cool temperate steppe",
        "Cool temperate desert scrub",
        "Cool temperate desert",
        "Cool temperate desert",
    ),
    # warm temperate (model bin 12–24 °C also covers subtropical range)
    (
        "Warm temperate rain forest",
        "Warm temperate wet forest",
        "Warm temperate moist forest",
        "Warm temperate dry forest",
        "Warm temperate thorn scrub",
        "Warm temperate desert scrub",
        "Warm temperate desert",
    ),
    # tropical (≥ 24 °C)
    (
        "Tropical rain forest",
        "Tropical wet forest",
        "Tropical moist forest",
        "Tropical dry forest",
        "Tropical thorn woodland",
        "Tropical desert scrub",
        "Tropical desert",
    ),
)

ZONE_NAMES: dict[int, str] = {
    int(HoldridgeOverride.OCEAN): "Ocean",
    int(HoldridgeOverride.LAKE): "Lake",
    int(HoldridgeOverride.ICE): "Permanent ice",
    int(HoldridgeOverride.ALPINE_BARE): "Alpine bare",
}


def _bio_bin(bio: NDArray[np.floating]) -> NDArray[np.int16]:
    b = np.asarray(bio, dtype=np.float64)
    out = np.full(b.shape, len(_BIO_EDGES), dtype=np.int16)
    out[b < _BIO_EDGES[0]] = 0
    for i in range(len(_BIO_EDGES) - 1):
        out[(b >= _BIO_EDGES[i]) & (b < _BIO_EDGES[i + 1])] = i + 1
    out[b >= _BIO_EDGES[-1]] = len(_BIO_EDGES)
    return out


def _hum_bin(ratio: NDArray[np.floating]) -> NDArray[np.int16]:
    r = np.asarray(ratio, dtype=np.float64)
    out = np.full(r.shape, len(_PET_EDGES), dtype=np.int16)
    out[r < _PET_EDGES[0]] = 0
    for i in range(len(_PET_EDGES) - 1):
        out[(r >= _PET_EDGES[i]) & (r < _PET_EDGES[i + 1])] = i + 1
    out[r >= _PET_EDGES[-1]] = len(_PET_EDGES)
    return out


def life_zone_id(bio_bin: int, hum_bin: int) -> int:
    """Encode latitudinal × humidity bins into a compact positive zone id (≥ 10)."""
    return 10 + int(bio_bin) * 10 + int(hum_bin)


def life_zone_display_name(bio_bin: int, hum_bin: int) -> str:
    bi = int(np.clip(bio_bin, 0, len(_LIFE_ZONE_DISPLAY) - 1))
    hi = int(np.clip(hum_bin, 0, len(_LIFE_ZONE_DISPLAY[0]) - 1))
    return _LIFE_ZONE_DISPLAY[bi][hi]


def build_zone_legend() -> dict[str, str]:
    """id → display label (Wikipedia-style life-zone names + overrides)."""
    legend = {str(k): v for k, v in ZONE_NAMES.items()}
    for bi in range(len(_LIFE_ZONE_DISPLAY)):
        for hi in range(len(_LIFE_ZONE_DISPLAY[0])):
            zid = life_zone_id(bi, hi)
            legend[str(zid)] = life_zone_display_name(bi, hi)
    return legend


def humanize_zone_label(raw: str) -> str:
    """Pass through display names; legacy ``boreal__humid`` still readable."""
    text = str(raw).strip()
    if not text:
        return "Unknown"
    if "__" in text or (text.islower() and "_" in text):
        text = text.replace("__", " / ").replace("_", " ")
        return text[:1].upper() + text[1:]
    return text


def zone_label_for_id(zone_id: int, legend: dict[str, str] | None = None) -> str:
    zid = int(zone_id)
    leg = legend if legend is not None else build_zone_legend()
    if str(zid) in leg:
        return humanize_zone_label(leg[str(zid)])
    if zid >= 10:
        code = zid - 10
        return life_zone_display_name(code // 10, code % 10)
    return f"Zone {zid}"


def classify_holdridge(
    *,
    biotemperature_c: NDArray[np.floating],
    pet_ratio_field: NDArray[np.floating],
    ocean_mask: NDArray[np.bool_],
    elevation_m: NDArray[np.floating],
    lake_mask: NDArray[np.bool_] | None = None,
    ice_biotemp_max_c: float = 1.5,
    alpine_elev_m: float = 3500.0,
) -> tuple[NDArray[np.int16], NDArray[np.int16]]:
    """Return ``(holdridge_zone_id, override_code)``.

    ``override_code`` is 0 for classified land life zones; otherwise matches
    :class:`HoldridgeOverride` values.
    """
    ocean = np.asarray(ocean_mask, dtype=np.bool_)
    bio = np.asarray(biotemperature_c, dtype=np.float64)
    ratio = np.asarray(pet_ratio_field, dtype=np.float64)
    elev = np.asarray(elevation_m, dtype=np.float64)
    lakes = (
        np.asarray(lake_mask, dtype=np.bool_)
        if lake_mask is not None
        else np.zeros(ocean.shape, dtype=bool)
    )

    bio_b = _bio_bin(bio)
    hum_b = _hum_bin(ratio)
    zones = (10 + bio_b * 10 + hum_b).astype(np.int16)
    override = np.zeros(ocean.shape, dtype=np.int16)

    # Overrides (priority: ocean > lake > ice > alpine)
    alpine = (~ocean) & (elev >= alpine_elev_m) & (bio < 6.0)
    ice = (~ocean) & (bio < ice_biotemp_max_c) & ~alpine
    zones = np.where(alpine, int(HoldridgeOverride.ALPINE_BARE), zones)
    override = np.where(alpine, int(HoldridgeOverride.ALPINE_BARE), override)
    zones = np.where(ice, int(HoldridgeOverride.ICE), zones)
    override = np.where(ice, int(HoldridgeOverride.ICE), override)
    zones = np.where(lakes & ~ocean, int(HoldridgeOverride.LAKE), zones)
    override = np.where(lakes & ~ocean, int(HoldridgeOverride.LAKE), override)
    zones = np.where(ocean, int(HoldridgeOverride.OCEAN), zones)
    override = np.where(ocean, int(HoldridgeOverride.OCEAN), override)

    return zones, override
