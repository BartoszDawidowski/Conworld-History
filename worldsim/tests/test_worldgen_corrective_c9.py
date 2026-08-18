"""C9 — BiomeV2 / landform display modes, legends, inspection grid, Godot wiring."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import numpy as np

from worldsim.export.atlas_display import (
    PRIMARY_MODE_DESCRIPTORS,
    paint_categorical_rgb,
)
from worldsim.export.inspection_grid import (
    decode_inspection_value,
    encode_inspection_grid,
)
from worldsim.export.pngutil import write_png_rgb
from worldsim.physical.ecology.biome_v2 import (
    BIOME_V2_DISPLAY_CLASSES,
    BIOME_V2_LEGEND_SCHEMA,
    BIOME_V2_LEGEND_TITLE,
    CLASS_NAMES,
    biome_v2_legend,
)
from worldsim.physical.landforms.classify import (
    BroadContext,
    DisplayLandform,
    LANDFORM_DISPLAY_CLASSES,
    derive_display_landform_id,
    landform_display_legend,
    legend_payload,
)

ROOT = Path(__file__).resolve().parents[2]
GODOT = ROOT / "godot"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    text = str(color).lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _read_png_rgb(path: Path) -> np.ndarray:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    width = height = color_type = None
    idat = b""
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, _bit, color_type = struct.unpack(">IIBB", chunk[:10])
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
    assert width and height and color_type == 2
    raw = zlib.decompress(idat)
    stride = 1 + width * 3
    rows = []
    for j in range(height):
        row = raw[j * stride : (j + 1) * stride]
        assert row[0] == 0
        rows.append(np.frombuffer(row[1:], dtype=np.uint8).reshape(width, 3))
    return np.stack(rows, axis=0)


def test_biome_v2_palette_matches_legend_and_png(tmp_path: Path) -> None:
    legend = biome_v2_legend()
    assert legend["schema"] == BIOME_V2_LEGEND_SCHEMA
    assert legend["title"] == BIOME_V2_LEGEND_TITLE
    ids = np.arange(7, dtype=np.uint8).reshape(1, 7)
    rgb = paint_categorical_rgb(ids, legend["classes"])
    for i, spec in BIOME_V2_DISPLAY_CLASSES.items():
        assert tuple(rgb[0, i]) == _hex_to_rgb(spec["color"])
    path = tmp_path / "biome_v2.png"
    write_png_rgb(path, rgb)
    decoded = _read_png_rgb(path)
    assert np.array_equal(decoded, rgb)


def test_landform_display_priority_and_palette() -> None:
    ctx = np.full((4, 4), int(BroadContext.PLAIN), dtype=np.uint8)
    ctx[0, :] = int(BroadContext.OCEAN)
    ctx[1, 0] = int(BroadContext.UPLAND)
    ctx[1, 1] = int(BroadContext.BASIN)
    ctx[1, 2] = int(BroadContext.PLATEAU)
    range_id = np.zeros((4, 4), dtype=np.int32)
    plateau_id = np.zeros((4, 4), dtype=np.int32)
    range_id[1, 3] = 9
    range_id[2, 0] = 9  # overlap with plateau object
    plateau_id[2, 0] = 4
    plateau_id[2, 1] = 4
    range_id[0, 1] = 3  # ocean still wins
    display, diag = derive_display_landform_id(
        ctx,
        mountain_range_id=range_id,
        plateau_id=plateau_id,
        ocean_mask=ctx == int(BroadContext.OCEAN),
    )
    assert display[0, 0] == int(DisplayLandform.OCEAN)
    assert display[0, 1] == int(DisplayLandform.OCEAN)
    assert display[1, 0] == int(DisplayLandform.UPLAND)
    assert display[1, 1] == int(DisplayLandform.BASIN)
    assert display[1, 2] == int(DisplayLandform.PLATEAU)
    assert display[1, 3] == int(DisplayLandform.MOUNTAIN)
    assert display[2, 0] == int(DisplayLandform.MOUNTAIN)
    assert display[2, 1] == int(DisplayLandform.PLATEAU)
    assert display[3, 0] == int(DisplayLandform.PLAIN)
    assert diag["range_plateau_overlap_cells"] == 1
    rgb = paint_categorical_rgb(display, landform_display_legend()["display_classes"])
    assert tuple(rgb[1, 3]) == _hex_to_rgb(LANDFORM_DISPLAY_CLASSES[3]["color"])
    assert tuple(rgb[0, 0]) == _hex_to_rgb(LANDFORM_DISPLAY_CLASSES[0]["color"])


def test_c8_canonical_legend_payload_unchanged() -> None:
    payload = legend_payload()
    assert payload["broad_context"][0] == "ocean"
    assert "color" not in str(payload["broad_context"])
    assert CLASS_NAMES[3] == "growing_moist"


def test_inspection_grid_roundtrip_includes_nan() -> None:
    temp = np.array([[1.5, np.nan], [2.25, -3.0]], dtype=np.float64)
    precip = np.array([[0.5, 1.0], [0.0, 2.0]], dtype=np.float64)
    humid = np.array([[0.4, 0.5], [np.nan, 0.9]], dtype=np.float64)
    blob, schema = encode_inspection_grid(
        temperature=temp,
        precipitation=precip,
        humidity=humid,
        precip_scale_mm=200.0,
    )
    assert schema["layout"] == "field_major, month_major, hex"
    assert decode_inspection_value(blob, schema, "temperature_c", month=0, hex_id=0) == 1.5
    assert np.isnan(
        decode_inspection_value(blob, schema, "temperature_c", month=1, hex_id=0)
    )
    assert decode_inspection_value(
        blob, schema, "precipitation_mm_or_proxy", month=0, hex_id=0
    ) == 100.0
    assert np.isnan(
        decode_inspection_value(blob, schema, "humidity_rh_proxy", month=0, hex_id=1)
    )


def test_atlas_export_structured_modes_and_png_colours(tmp_path: Path) -> None:
    from test_worldgen_corrective_c8 import _bundle
    from worldsim.export import export_atlas_display

    model, *_rest = _bundle()
    out = tmp_path / "atlas_display"
    meta = export_atlas_display(model, out)
    assert meta["schema"] == "atlas_display_v2"
    assert all(isinstance(item, dict) for item in meta["map_modes"])
    ids = [str(item["id"]) for item in meta["map_modes"]]
    assert ids == [str(d["id"]) for d in PRIMARY_MODE_DESCRIPTORS if d["id"] in ids]
    assert "biome_v2" in ids
    assert "landforms" in ids
    biome_leg = json.loads((out / "biome_v2_legend.json").read_text(encoding="utf-8"))
    land_leg = json.loads((out / "landform_legend.json").read_text(encoding="utf-8"))
    biome_png = _read_png_rgb(out / "biome_v2.png")
    land_png = _read_png_rgb(out / "landforms.png")
    biome_colours = {_hex_to_rgb(spec["color"]) for spec in biome_leg["classes"].values()}
    land_colours = {
        _hex_to_rgb(spec["color"]) for spec in land_leg["display_classes"].values()
    }
    for pix in np.unique(biome_png.reshape(-1, 3), axis=0):
        assert tuple(int(c) for c in pix) in biome_colours
    present = set()
    for pix in np.unique(land_png.reshape(-1, 3), axis=0):
        tup = tuple(int(c) for c in pix)
        assert tup in land_colours
        for key, spec in land_leg["display_classes"].items():
            if tup == _hex_to_rgb(spec["color"]):
                present.add(int(key))
    assert 0 in present  # ocean
    rid = np.asarray(model.rasters.get("landforms/mountain_range_id"))
    if np.any(rid > 0):
        assert 3 in present  # accepted range object wins display class
    summary = json.loads((out / "climate_summary.json").read_text(encoding="utf-8"))
    assert "temperature_integrity_ok" in summary
    assert (out / "inspection_grid.bin").is_file()


def test_godot_c9_display_contract() -> None:
    modes = (GODOT / "atlas" / "MapModeController.gd").read_text(encoding="utf-8")
    assert '"biome_v2"' in modes
    assert '"landforms"' in modes
    assert "configure_from_meta" in modes
    assert "TYPE_DICTIONARY" in modes
    raster = (GODOT / "atlas" / "RasterLayerRenderer.gd").read_text(encoding="utf-8")
    apply = raster[raster.find("func apply_mode") :]
    assert apply.find("file_exists") < apply.find("_mode = requested")
    assert "TEXTURE_FILTER_LINEAR" in raster
    land = (GODOT / "atlas" / "LandLayerRenderer.gd").read_text(encoding="utf-8")
    assert "biome_v2" in land
    assert "sample_nearest" in land
    assert "mode_blur_texels" in land
    lf = (GODOT / "atlas" / "LandformLayerRenderer.gd").read_text(encoding="utf-8")
    assert "_chaikin_open_px" in lf
    assert "_chaikin_closed_px" in lf
    atlas = (GODOT / "atlas" / "WorldAtlas.gd").read_text(encoding="utf-8")
    assert "inspect_feature" in atlas
    lake_i = atlas.find("pick_lake")
    river_i = atlas.find("pick_river")
    lf_i = atlas.find("landforms.pick")
    hex_i = atlas.find("hex_info")
    assert 0 <= lake_i < river_i < lf_i < hex_i
    assert (GODOT / "atlas" / "LandformLayerRenderer.gd").is_file()
    assert (GODOT / "atlas" / "LegendPanel.gd").is_file()
    main_gd = (GODOT / "scenes" / "Main.gd").read_text(encoding="utf-8")
    assert "biome_v2" in main_gd
    assert "landforms" in main_gd
    assert "Landform objects" in (GODOT / "scenes" / "Main.tscn").read_text(
        encoding="utf-8"
    ) or "LandformCheck" in (GODOT / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    tscn = (GODOT / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    assert "LandformCheck" in tscn
    assert "LegendPanel.gd" in tscn
    forbidden = [
        "#5E8B57",
        "#D1A466",
        "#397A72",
        "#D8D0AA",
        "#A99063",
        "#736357",
        "#B87855",
        "#8E9E78",
        "mountain_score_threshold",
    ]
    for rel in (
        "atlas/LandformLayerRenderer.gd",
        "atlas/LegendPanel.gd",
        "atlas/RasterLayerRenderer.gd",
        "atlas/MapModeController.gd",
        "atlas/InspectorPanel.gd",
        "atlas/HexOverlayRenderer.gd",
        "atlas/WorldAtlas.gd",
    ):
        text = (GODOT / rel).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} in {rel}"
    vectors = (GODOT / "atlas" / "VectorLayerRenderer.gd").read_text(encoding="utf-8")
    assert "func pick_lake" in vectors
    hexes = (GODOT / "atlas" / "HexOverlayRenderer.gd").read_text(encoding="utf-8")
    assert "inspection_grid.bin" in hexes
    assert "biome_v2_dominant" in hexes
    insp = (GODOT / "atlas" / "InspectorPanel.gd").read_text(encoding="utf-8")
    assert "No data" in hexes or "No data" in insp
    assert "_format_lake" in insp
    assert "show_feature" in insp
