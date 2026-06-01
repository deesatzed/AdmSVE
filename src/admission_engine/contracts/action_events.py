"""Action-events schema: orders/treatments with clinical-indication tags.

Each candidate action carries a clinical-indication tag describing whether the action is
independently warranted for this patient regardless of billing. The integrity gate uses this
(via the independent clinical-indication judge) to suppress status-helpful-but-not-indicated
actions (handoff §3.1, Invariant 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Clinical-indication tags. Only INDICATED actions may ever be surfaced as "new testing/treatment".
INDICATION_TAGS = {
    "independently_indicated",  # warranted regardless of billing -> may pass the gate
    "not_independently_indicated",  # helps status only -> MUST be suppressed
    "documentation_of_existing_fact",  # not new care; captures necessity that already exists
    "indicated_pending",  # already-ordered/indicated workup that will also clarify status
    "unknown",  # insufficient info -> treated as not-indicated by the gate (fail closed)
}


@dataclass(frozen=True)
class ActionEvent:
    action_id: str
    description: str
    indication_tag: str
    present: bool  # whether the action/documentation is already present in the record
    timestamp: str | None = None
    raw: dict[str, Any] | None = None

    @property
    def is_new_care(self) -> bool:
        """True if surfacing this would constitute recommending NEW testing/treatment."""
        return self.indication_tag in {
            "independently_indicated",
            "not_independently_indicated",
            "indicated_pending",
            "unknown",
        } and not self.present


def parse_action_events(actions: list[dict[str, Any]] | None) -> list[ActionEvent]:
    events: list[ActionEvent] = []
    for idx, raw in enumerate(actions or []):
        tag = raw.get("clinical_indication_tag", "unknown")
        if tag not in INDICATION_TAGS:
            tag = "unknown"
        events.append(
            ActionEvent(
                action_id=raw.get("action_id", f"action-{idx:03d}"),
                description=raw.get("description", ""),
                indication_tag=tag,
                present=bool(raw.get("present", False)),
                timestamp=raw.get("timestamp"),
                raw=raw,
            )
        )
    return events
