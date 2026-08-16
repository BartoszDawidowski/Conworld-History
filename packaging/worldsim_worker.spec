# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for worldsim_worker (Milestone 18).

Build from repo root via packaging/build_*. scripts so paths resolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR.parent
WORLDSIM = ROOT / "worldsim"
SRC = WORLDSIM / "src"
CONFIGS = WORLDSIM / "configs"
LICENSES = ROOT / "licenses"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
ENTRY = SRC / "worldsim" / "__main__.py"

datas = [
    (str(CONFIGS), "configs"),
    (str(LICENSES), "licenses"),
    (str(NOTICES), "."),
]
binaries: list = []
hiddenimports = [
    "platec",
    "pyflwdir",
    "yaml",
    "numpy",
    "numba",
    "llvmlite",
    "worldsim",
    "worldsim.cli",
    "worldsim.pipeline",
]

for pkg in ("numba", "llvmlite", "pyflwdir", "scipy"):
    try:
        tmp_datas, tmp_bins, tmp_hidden = collect_all(pkg)
        datas += tmp_datas
        binaries += tmp_bins
        hiddenimports += tmp_hidden
    except Exception as exc:  # noqa: BLE001 — packaging best-effort
        print(f"warning: collect_all({pkg!r}) failed: {exc}", file=sys.stderr)

hiddenimports += [
    "scipy._external.array_api_compat.numpy",
    "scipy._external.array_api_compat.numpy.fft",
]

# Vendored platec extension (.so / .pyd) — importable if on PYTHONPATH during Analysis
try:
    import platec as _platec

    platec_file = Path(_platec.__file__)
    if platec_file.suffix in {".so", ".pyd", ".dll"} or ".cpython-" in platec_file.name:
        binaries.append((str(platec_file), "."))
except Exception as exc:  # noqa: BLE001
    print(f"warning: could not locate platec binary: {exc}", file=sys.stderr)

datas += collect_data_files("worldsim", includes=["**/*.yaml", "**/*.yml"])

block_cipher = None

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC), str(ROOT / "vendor" / "pyplatec")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="worldsim_worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="worldsim_worker",
)
