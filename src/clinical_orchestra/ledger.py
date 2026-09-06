"""Append-only run ledger.

Every run writes a directory containing a manifest (what was run, with which models and settings),
an append-only event log, and any number of named JSONL streams. Nothing is overwritten and nothing
is written in place, so a partial or crashed run is visible rather than silently truncated.

This is the v1 ledger with the diagnosis-specific schemas removed: callers pass plain dicts, so the
same ledger works for timeline extraction, evaluation runs, and scoring.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


class RunLedger:
    """Writes a manifest, an event log, and named JSONL streams for one run."""

    def __init__(self, run_dir: Path, manifest: dict[str, Any]) -> None:
        self.run_dir = run_dir
        self.manifest = manifest
        # exist_ok=False: a run never writes into an existing run directory, so results from two
        # runs can't be silently interleaved.
        self.run_dir.mkdir(parents=True, exist_ok=False)
        (self.run_dir / "events.jsonl").touch(exist_ok=False)
        self.write_manifest()

    @classmethod
    def create(
        cls,
        *,
        out_dir: str | Path,
        mode: str,
        run_id: str | None = None,
        config: dict[str, Any] | None = None,
        source_exclusion: dict[str, Any] | None = None,
        git_commit: str | None = None,
    ) -> "RunLedger":
        """Start a run.

        `config` should record everything needed to reproduce the run: model ids, temperature,
        sample counts, prompt version, dataset path and size. `source_exclusion` records the
        contamination controls actually applied (the DOIs/PMCIDs/titles withheld from retrieval).
        """
        resolved_run_id = run_id or make_run_id()
        run_dir = Path(out_dir).expanduser().resolve() / resolved_run_id
        manifest = {
            "run_id": resolved_run_id,
            "mode": mode,
            "started_at": utc_now(),
            "status": "running",
            "run_dir": str(run_dir),
            "config": config or {},
            "source_exclusion": source_exclusion or {},
            "git_commit": git_commit,
            "python_version": sys.version.split()[0],
        }
        ledger = cls(run_dir, manifest)
        ledger.append_event(actor="runner", action="run_created", details={"mode": mode})
        return ledger

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    def update_manifest(self, **changes: Any) -> None:
        self.manifest.update(changes)
        self.write_manifest()

    def finish(self, *, status: str = "completed", **changes: Any) -> None:
        self.update_manifest(status=status, finished_at=utc_now(), **changes)
        self.append_event(actor="runner", action="run_finished", details={"status": status})

    def write_manifest(self) -> None:
        write_json(self.manifest_path, self.manifest)

    def append_event(
        self,
        *,
        actor: str,
        action: str,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": f"event:{uuid.uuid4().hex}",
            "timestamp": utc_now(),
            "actor": actor,
            "action": action,
            "details": details or {},
            "error": error,
        }
        self.append("events", event)
        return event

    def append(self, stream: str, payload: dict[str, Any]) -> None:
        """Append one record to `<run_dir>/<stream>.jsonl`."""
        path = self.run_dir / f"{stream}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def write_json(self, name: str, payload: Any) -> Path:
        """Write (or replace) a named JSON file in the run directory."""
        path = self.run_dir / name
        write_json(path, payload)
        return path


def write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically, so an interrupted write leaves the old file intact."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    tmp_path.replace(path)
