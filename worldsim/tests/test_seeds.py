from __future__ import annotations

from worldsim.seeds import DEFAULT_MODULE_NAMES, build_seed_manifest, derive_seed


def test_derive_seed_is_deterministic() -> None:
    a = derive_seed(183716, "tectonics", 2)
    b = derive_seed(183716, "tectonics", 2)
    assert a == b
    assert a.bit_length() <= 64


def test_named_seeds_differ_by_module() -> None:
    tectonics = derive_seed(183716, "tectonics", 2)
    climate = derive_seed(183716, "climate", 2)
    assert tectonics != climate


def test_adding_module_does_not_change_existing_seeds() -> None:
    base = build_seed_manifest(42, module_names=("tectonics", "climate"))
    extended = build_seed_manifest(
        42, module_names=("tectonics", "climate", "brand_new_module")
    )
    assert base.modules["tectonics"] == extended.modules["tectonics"]
    assert base.modules["climate"] == extended.modules["climate"]


def test_schema_version_changes_seeds() -> None:
    v2 = derive_seed(1, "tectonics", 2)
    v3 = derive_seed(1, "tectonics", 3)
    assert v2 != v3


def test_default_manifest_covers_architecture_modules() -> None:
    manifest = build_seed_manifest(183716)
    assert set(manifest.modules) == set(DEFAULT_MODULE_NAMES)
    assert manifest.master_seed == 183716
    assert manifest.schema_version == 2
