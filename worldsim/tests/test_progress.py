from __future__ import annotations

import json
from io import StringIO

import pytest

from worldsim.progress import ProgressReporter, parse_ndjson_line


def test_progress_emits_valid_ndjson_sequence() -> None:
    buf = StringIO()
    reporter = ProgressReporter(stream=buf)
    reporter.started(seed=183716, schema_version=2)
    reporter.stage_started("tectonics")
    reporter.progress("tectonics", 0.42)
    reporter.stage_complete("tectonics")
    reporter.complete("/tmp/world")

    lines = [line for line in buf.getvalue().splitlines() if line]
    events = [parse_ndjson_line(line)["event"] for line in lines]
    assert events == [
        "started",
        "stage_started",
        "progress",
        "stage_complete",
        "complete",
    ]
    progress = json.loads(lines[2])
    assert progress["value"] == 0.42


def test_progress_rejects_out_of_range() -> None:
    reporter = ProgressReporter(stream=StringIO())
    with pytest.raises(ValueError):
        reporter.progress("tectonics", 1.5)


def test_error_event_shape() -> None:
    buf = StringIO()
    reporter = ProgressReporter(stream=buf)
    reporter.error(
        code="HYDROLOGY_FAILED",
        message="boom",
        stage="hydrology",
        trace_path="/tmp/error.log",
    )
    record = parse_ndjson_line(buf.getvalue())
    assert record["event"] == "error"
    assert record["code"] == "HYDROLOGY_FAILED"
    assert record["stage"] == "hydrology"
