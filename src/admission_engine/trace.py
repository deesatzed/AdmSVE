"""Hash-chained trace output for admission-engine runs.

Reused from the sibling ClinClaw/EMEX project. Each adjudication event is hash-chained to the
previous one so the full provenance ledger is tamper-evident (handoff Invariant 6: snapshot every
adjudication with response + version + timestamp).

A fixed timestamp may be injected (``now``) so corpus runs and reproducibility tests are
byte-deterministic; production runs use wall-clock time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .hashing import hash_json


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Trace:
    session_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    clock: Callable[[], str] = _utcnow_iso

    def add(self, event_type: str, data: dict[str, Any]) -> None:
        prev_hash = self.events[-1]["event_hash"] if self.events else "0" * 64
        event = {
            "event_id": f"trace-{len(self.events) + 1:04d}",
            "event_type": event_type,
            "timestamp": self.clock(),
            "data": data,
            "prev_hash": prev_hash,
        }
        event["event_hash"] = hash_json(event)
        self.events.append(event)

    def render(self) -> dict[str, Any]:
        return {
            "schema_version": "admission_engine.trace.v0.1",
            "session_id": self.session_id,
            "event_count": len(self.events),
            "events": self.events,
        }

    def verify(self) -> tuple[bool, str]:
        prev_hash = "0" * 64
        for idx, event in enumerate(self.events):
            if event.get("prev_hash") != prev_hash:
                return False, f"event {idx} prev_hash mismatch"
            event_copy = {k: v for k, v in event.items() if k != "event_hash"}
            if hash_json(event_copy) != event.get("event_hash"):
                return False, f"event {idx} event_hash mismatch"
            prev_hash = event["event_hash"]
        return True, "trace verified"

    def to_json(self) -> str:
        return json.dumps(self.render(), indent=2)
