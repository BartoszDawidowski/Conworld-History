"""Newline-delimited JSON progress / control protocol for Godot ↔ worker."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Mapping, TextIO


@dataclass
class ProgressReporter:
    """Writes architecture §9 NDJSON events to a stream (default: stdout)."""

    stream: TextIO = field(default_factory=lambda: sys.stdout)
    _closed: bool = field(default=False, init=False, repr=False)

    def emit(self, event: str, **payload: Any) -> None:
        if self._closed:
            raise RuntimeError("ProgressReporter is closed")
        record: dict[str, Any] = {"event": event, **payload}
        self.stream.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")))
        self.stream.write("\n")
        self.stream.flush()

    def started(self, *, seed: int, schema_version: int) -> None:
        self.emit("started", seed=seed, schema_version=schema_version)

    def stage_started(self, stage: str) -> None:
        self.emit("stage_started", stage=stage)

    def progress(self, stage: str, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"progress value must be in [0, 1], got {value}")
        self.emit("progress", stage=stage, value=float(value))

    def stage_complete(self, stage: str) -> None:
        self.emit("stage_complete", stage=stage)

    def complete(self, world_path: str) -> None:
        self.emit("complete", world_path=world_path)

    def error(
        self,
        *,
        code: str,
        message: str,
        stage: str | None = None,
        trace_path: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"code": code, "message": message}
        if stage is not None:
            payload["stage"] = stage
        if trace_path is not None:
            payload["trace_path"] = trace_path
        self.emit("error", **payload)

    def close(self) -> None:
        self._closed = True


def parse_ndjson_line(line: str) -> Mapping[str, Any]:
    """Parse one protocol line; raises ValueError on invalid records."""
    text = line.strip()
    if not text:
        raise ValueError("empty NDJSON line")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("NDJSON record must be an object")
    if "event" not in data or not isinstance(data["event"], str):
        raise ValueError("NDJSON record requires string 'event'")
    return data
