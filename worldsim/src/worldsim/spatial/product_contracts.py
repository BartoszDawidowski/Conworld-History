"""PC6 — versioned product field lists shared by save/load, export, and parity probes."""

from __future__ import annotations

from worldsim.spatial.hex_grid.contract import HEX_CONTRACT_FIELDS

PRODUCT_CONTRACT_VERSION = "pc6_product_contract_v1"
INSPECTOR_CONTRACT_VERSION = "pc6_inspector_status_v1"

PERSISTED_CRYOSPHERE_RASTERS: tuple[str, ...] = (
    "cryosphere/seasonal_snow_swe",
    "cryosphere/firn_swe",
    "cryosphere/soil_water",
)

# Hydrology rasters that must round-trip through WorldSpatialModel save/load.
PERSISTED_HYDROLOGY_RASTERS: tuple[str, ...] = (
    "hydrology/river_mask",
    "hydrology/lake_mask",
    "hydrology/basin_envelope_id",
    "hydrology/water_fraction_mean",
    "hydrology/water_fraction_monthly",
    "hydrology/open_water_fraction_monthly",
    "hydrology/lake_ice_fraction_monthly",
    "hydrology/channel_state",
    "hydrology/basin_id",
    "hydrology/lake_id",
    "hydrology/flow_accumulation",
    "hydrology/flow_direction",
    "hydrology/river_discharge_proxy",
    "hydrology/river_discharge_gross",
    "hydrology/channel_mask",
    "hydrology/geomorphic_channel_mask",
    "hydrology/display_river_mask",
)

# PC2 three-tier network masks (subset of hydrology rasters).
CHANNEL_TIER_RASTERS: tuple[str, ...] = (
    "hydrology/channel_mask",
    "hydrology/geomorphic_channel_mask",
    "hydrology/display_river_mask",
)

# Diagnostic PNG layers exported under atlas_display/ (§10.2 minimal PC6 set).
DIAGNOSTIC_LAYER_DESCRIPTORS: tuple[dict[str, str], ...] = (
    {
        "id": "log_catchment",
        "label": "Log catchment area",
        "file": "log_catchment_area.png",
        "domain": "hydrology",
    },
    {
        "id": "geomorphic_channel",
        "label": "Geomorphic channel network",
        "file": "geomorphic_channel.png",
        "domain": "hydrology",
    },
    {
        "id": "display_river",
        "label": "Display river network",
        "file": "display_river.png",
        "domain": "hydrology",
    },
)

DIAGNOSTIC_LAYER_IDS: tuple[str, ...] = tuple(d["id"] for d in DIAGNOSTIC_LAYER_DESCRIPTORS)

HEX_EXPORT_CONTRACT_FIELDS: tuple[str, ...] = HEX_CONTRACT_FIELDS
# Columnar atlas export omits hex_id (implicit cell index).
HEX_EXPORT_COLUMN_FIELDS: tuple[str, ...] = tuple(
    f for f in HEX_CONTRACT_FIELDS if f != "hex_id"
)
