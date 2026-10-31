"""Append-only audit trail for the agent team (output/audit_trail.json).

The file holds a list of runs. A new run is only ever appended; earlier runs
are never edited or removed. Each run stores the hash of the run before it
and its own hash, so any later edit to an earlier run is detected and the
next run refuses to write until it is fixed.
"""

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

FILE_DESCRIPTION = (
    "Append-only audit trail of the Campus Customs agent team (HW5 Problem 5). "
    "Each run is appended; earlier runs are never changed. run_hash covers the whole run, "
    "and prev_run_hash links it to the run before it."
)
_APPEND_LOCK = threading.Lock()  # an agent run and a human action may finish at the same time


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _hash(run: dict) -> str:
    body = {k: v for k, v in run.items() if k != "run_hash"}
    body = json.loads(json.dumps(body, default=str))  # hash exactly what is stored in the file
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_trail(path: Path) -> dict:
    """Read the trail and confirm no earlier run was altered."""
    if not path.exists():
        return {"description": FILE_DESCRIPTION, "runs": []}
    trail = json.loads(path.read_text(encoding="utf-8"))
    prev = None
    for i, run in enumerate(trail.get("runs", [])):
        if run.get("prev_run_hash") != prev or run.get("run_hash") != _hash(run):
            raise RuntimeError(f"Audit trail check failed at run {i} ({run.get('run_id')}); refusing to append.")
        prev = run["run_hash"]
    return trail


class RunAudit:
    """Collects the events of one run, then appends the run to the trail."""

    def __init__(self, path: Path, mode: str, settings: dict[str, Any],
                 listener: Callable[[str, dict], None] | None = None):
        """`listener(run_id, event)` sees each event as it happens (the dashboard's live view)."""
        self.path = path
        self.listener = listener
        load_trail(path)  # fail early if the existing trail was tampered with
        self.run: dict[str, Any] = {
            "run_id": f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}",
            "started_at": _now(),
            "mode": mode,
            "settings": settings,
            "events": [],
        }

    @property
    def run_id(self) -> str:
        return self.run["run_id"]

    def log(self, event: str, agent: str | None = None, ticket_id: int | None = None, **data: Any) -> None:
        entry = {
            "seq": len(self.run["events"]) + 1,
            "at": _now(),
            "event": event,
            "agent": agent,
            "ticket_id": ticket_id,
            **data,
        }
        self.run["events"].append(entry)
        if self.listener is not None:
            self.listener(self.run_id, entry)

    def append_to_trail(self, status: str, **summary: Any) -> None:
        """Append this run to the file. Earlier runs are copied over unchanged."""
        with _APPEND_LOCK:
            trail = load_trail(self.path)
            runs = trail.setdefault("runs", [])
            self.run.update(finished_at=_now(), status=status, **summary)
            self.run["prev_run_hash"] = runs[-1]["run_hash"] if runs else None
            self.run["run_hash"] = _hash(self.run)
            runs.append(self.run)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(trail, indent=2, default=str) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)


def log_human_action(path: Path, action: str, status: str = "ok", ticket_id: int | None = None,
                     **data: Any) -> str:
    """Append a one-event entry for something a human did (approve, reject, reset)."""
    audit = RunAudit(path, mode=f"human action: {action}", settings={})
    audit.log(f"human_{action}", None, ticket_id, **data)
    audit.append_to_trail(status)
    return audit.run_id
