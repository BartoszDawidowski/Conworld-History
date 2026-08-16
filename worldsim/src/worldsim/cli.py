"""Command-line interface for the worldsim worker."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from worldsim import SCHEMA_VERSION, __version__
from worldsim.config import ConfigError, default_config_path, load_planet_config
from worldsim.pipeline import (
    run_atmosphere,
    run_climate,
    run_ecology,
    run_erosion,
    run_final,
    run_foundation,
    run_hex,
    run_hydrology,
    run_moisture,
    run_ocean,
    run_tectonics,
    run_terrain,
    run_vectors,
    run_world,
)
from worldsim.progress import ProgressReporter

STAGES = (
    "foundation",
    "tectonics",
    "terrain",
    "climate",
    "atmosphere",
    "ocean",
    "moisture",
    "erosion",
    "hydrology",
    "vectors",
    "final",
    "ecology",
    "hex",
    "world",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="worldsim",
        description="Conworld History physical-world simulation worker",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"worldsim {__version__} (schema {SCHEMA_VERSION})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="master generation seed",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to planet YAML config (default: packaged default_planet.yaml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="output directory for world artefacts / seed manifest",
    )
    parser.add_argument(
        "--stage",
        choices=STAGES,
        default=None,
        help="pipeline stage to run (default: world)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="alias for --stage foundation",
    )
    parser.add_argument(
        "--tectonics-width",
        type=int,
        default=None,
        help="override tectonics grid width (default: from config, 1024)",
    )
    parser.add_argument(
        "--tectonics-height",
        type=int,
        default=None,
        help="override tectonics grid height (default: from config, 512)",
    )
    parser.add_argument(
        "--terrain-width",
        type=int,
        default=None,
        help="override terrain production width",
    )
    parser.add_argument(
        "--terrain-height",
        type=int,
        default=None,
        help="override terrain production height",
    )
    parser.add_argument(
        "--climate-width",
        type=int,
        default=None,
        help="override climate grid width (default: from config, 1024)",
    )
    parser.add_argument(
        "--climate-height",
        type=int,
        default=None,
        help="override climate grid height (default: from config, 512)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    reporter = ProgressReporter(stream=sys.stdout)

    if args.dry_run and args.stage not in (None, "foundation"):
        reporter.error(
            code="STAGE_CONFLICT",
            message="--dry-run conflicts with --stage other than foundation",
            stage="bootstrap",
        )
        return 2

    stage = "foundation" if args.dry_run else (args.stage or "world")
    config_path = args.config if args.config is not None else default_config_path()
    try:
        config = load_planet_config(config_path)
        common_kw = dict(
            config=config,
            master_seed=args.seed,
            output_dir=args.output,
            reporter=reporter,
        )
        stage_kw = dict(
            width=args.tectonics_width,
            height=args.tectonics_height,
            terrain_width=args.terrain_width,
            terrain_height=args.terrain_height,
            climate_width=args.climate_width,
            climate_height=args.climate_height,
        )
        runners = {
            "foundation": lambda: run_foundation(**common_kw, dry_run=True),
            "tectonics": lambda: run_tectonics(
                **common_kw,
                width=args.tectonics_width,
                height=args.tectonics_height,
            ),
            "terrain": lambda: run_terrain(
                **common_kw,
                width=args.tectonics_width,
                height=args.tectonics_height,
                terrain_width=args.terrain_width,
                terrain_height=args.terrain_height,
            ),
            "climate": lambda: run_climate(**common_kw, **stage_kw),
            "atmosphere": lambda: run_atmosphere(**common_kw, **stage_kw),
            "ocean": lambda: run_ocean(**common_kw, **stage_kw),
            "moisture": lambda: run_moisture(**common_kw, **stage_kw),
            "erosion": lambda: run_erosion(**common_kw, **stage_kw),
            "hydrology": lambda: run_hydrology(**common_kw, **stage_kw),
            "vectors": lambda: run_vectors(**common_kw, **stage_kw),
            "final": lambda: run_final(**common_kw, **stage_kw),
            "ecology": lambda: run_ecology(**common_kw, **stage_kw),
            "hex": lambda: run_hex(**common_kw, **stage_kw),
            "world": lambda: run_world(**common_kw, **stage_kw),
        }
        runner = runners.get(stage)
        if runner is None:  # pragma: no cover
            reporter.error(
                code="STAGE_UNSUPPORTED",
                message=f"unsupported stage {stage!r}",
                stage="bootstrap",
            )
            return 2
        runner()
        return 0
    except ConfigError as exc:
        reporter.error(code="CONFIG_INVALID", message=str(exc), stage="bootstrap")
        return 2
    except Exception as exc:  # noqa: BLE001 — worker must always emit protocol errors
        trace_path = Path(args.output) / "error.log"
        try:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_path.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            trace_path = Path("error.log")
            trace_path.write_text(traceback.format_exc(), encoding="utf-8")
        reporter.error(
            code="WORKER_FAILED",
            message=str(exc),
            stage="bootstrap",
            trace_path=str(trace_path.resolve()),
        )
        return 1
    finally:
        reporter.close()


if __name__ == "__main__":
    raise SystemExit(main())
