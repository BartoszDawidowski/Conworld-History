from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from worldsim.pipeline import validate_seed_manifest_file
from worldsim.seeds import build_seed_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_cli_foundation_dry_run_and_deterministic_manifest(
    tmp_path: Path,
) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    config = ROOT / "configs" / "default_planet.yaml"

    def run(out: Path) -> list[dict]:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "worldsim",
                "--seed",
                "183716",
                "--config",
                str(config),
                "--output",
                str(out),
                "--stage",
                "foundation",
            ],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines]

    events_a = run(out_a)
    events_b = run(out_b)

    assert events_a[0]["event"] == "started"
    assert events_a[0]["seed"] == 183716
    assert events_a[-1]["event"] == "complete"
    assert {e["event"] for e in events_a} >= {
        "started",
        "stage_started",
        "stage_complete",
        "complete",
    }

    manifest_a = validate_seed_manifest_file(out_a / "seed_manifest.json")
    manifest_b = validate_seed_manifest_file(out_b / "seed_manifest.json")
    expected = build_seed_manifest(183716)
    assert manifest_a.to_dict() == expected.to_dict()
    assert manifest_b.to_dict() == expected.to_dict()


def test_cli_dry_run_alias(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "worldsim",
            "--seed",
            "1",
            "--output",
            str(tmp_path / "out"),
            "--dry-run",
        ],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "out" / "seed_manifest.json").is_file()
