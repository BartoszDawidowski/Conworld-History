#!/usr/bin/env bash
# Build macOS Apple Silicon / Intel worldsim_worker (Milestone 18).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/worldsim/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3.12 || true)"
fi
if [[ -z "${PYTHON}" ]]; then
  echo "python3.12 / worldsim .venv not found" >&2
  exit 1
fi

echo "Using $PYTHON"
if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PYTHON" -q "pyinstaller==6.14.2"
  else
    echo "pip missing and uv not found; cannot install pyinstaller" >&2
    exit 1
  fi
else
  "$PYTHON" -m pip install -q "pyinstaller==6.14.2"
fi
"$PYTHON" -c "import platec, pyflwdir, numpy; print('deps ok')"

export PYTHONPATH="$ROOT/worldsim/src${PYTHONPATH:+:$PYTHONPATH}"
rm -rf "$ROOT/packaging/build" "$ROOT/packaging/dist"
"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$ROOT/packaging/dist" \
  --workpath "$ROOT/packaging/build" \
  "$ROOT/packaging/worldsim_worker.spec"

WORKER="$ROOT/packaging/dist/worldsim_worker/worldsim_worker"
if [[ ! -x "$WORKER" ]]; then
  echo "missing $WORKER" >&2
  exit 1
fi

echo "Smoke: --help"
"$WORKER" --help >/dev/null
echo "Smoke: foundation dry-run"
OUT="$ROOT/packaging/dist/smoke_out"
rm -rf "$OUT"
"$WORKER" --seed 1 --output "$OUT" --stage foundation --dry-run
test -f "$OUT/seed_manifest.json"
echo "OK macOS worker → $WORKER"
