from __future__ import annotations

from pathlib import Path

from worldsim.config import default_config_path
from worldsim.runtime_paths import is_frozen, resource_path


ROOT = Path(__file__).resolve().parents[2]


def test_default_config_resolves() -> None:
    path = default_config_path()
    assert path.is_file()
    assert path.name == "default_planet.yaml"
    assert not is_frozen()


def test_resource_path_configs() -> None:
    path = resource_path("configs", "default_planet.yaml")
    assert path.is_file()


def test_packaging_skeleton_exists() -> None:
    assert (ROOT / "packaging" / "worldsim_worker.spec").is_file()
    assert (ROOT / "packaging" / "build_macos.sh").is_file()
    assert (ROOT / "packaging" / "build_windows.ps1").is_file()
    assert (ROOT / "packaging" / "README.md").is_file()
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()
    assert (ROOT / "docs" / "ADR" / "ADR-0003-pyinstaller-worldsim-worker.md").is_file()


def test_licence_notices_present() -> None:
    licenses = ROOT / "licenses"
    for name in (
        "GODOT_MIT.txt",
        "PYPLATEC_LGPL-3.0.txt",
        "PYFLWDIR_MIT.txt",
        "NUMPY_BSD.txt",
        "NUMBA_BSD.txt",
        "PYYAML_MIT.txt",
    ):
        assert (licenses / name).is_file(), name
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "PyInstaller" in notices
    assert "worldsim_worker" in notices or "Packaged" in notices
