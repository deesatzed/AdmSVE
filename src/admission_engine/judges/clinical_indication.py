"""Independent clinical-indication judge — the integrity-gate input.

Answers: "is this recommended action warranted for THIS patient regardless of billing?"
This judge is INDEPENDENT of the status-conformance judge (handoff Invariant 2, 8). An action that
passes only the status check but fails this check must be suppressed and logged — never surfaced.

In Phase 1 this is a deterministic stub reading the synthetic action's clinical-indication tag. It
is versioned and supports a leave-OE-out flag for the pre-registered sensitivity analysis
(Invariant 8): when leave_oe_out=True, OE-derived indication signals are dropped and the judge
falls back to non-OE guideline signals only (here, the fixture's explicit guideline tag).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..recommender.base import RecommendedAction


@dataclass(frozen=True)
class IndicationVerdict:
    action_id: str
    judge_id: str
    judge_version: str
    independently_indicated: bool
    gray_zone: bool  # ensemble disagreement
    rationale: str
    leave_oe_out: bool


class ClinicalIndicationJudge:
    judge_id = "clinical_indication"
    judge_version = "v0.1"
    # Backed by dotflows/clinical_indication_review.md (the integrity-gate judge).
    dotflow_role = "clinical_indication"

    def __init__(self, leave_oe_out: bool = False) -> None:
        self.leave_oe_out = leave_oe_out

    def evaluate(self, action: RecommendedAction, case_view: dict[str, Any]) -> IndicationVerdict:
        raw = {}
        # Find the originating fixture action to read independent guideline signal, if present.
        for a in case_view.get("actions", []) or []:
            if a.get("action_id") == action.action_id:
                raw = a
                break

        tag = action.indication_tag

        # Documentation of an existing fact is never "new care"; it is independently fine to surface.
        if tag == "documentation_of_existing_fact":
            return IndicationVerdict(
                action_id=action.action_id,
                judge_id=self.judge_id,
                judge_version=self.judge_version,
                independently_indicated=True,
                gray_zone=False,
                rationale="documentation of existing necessity; not new care",
                leave_oe_out=self.leave_oe_out,
            )

        # Independent guideline signal (non-OE). Used as the authority when leaving OE out.
        guideline_indicated = bool(raw.get("guideline_indicated", tag in {"independently_indicated", "indicated_pending"}))
        # OE ensemble signal (the OE-derived view).
        oe_indicated = bool(raw.get("oe_indicated", tag in {"independently_indicated", "indicated_pending"}))

        if self.leave_oe_out:
            indicated = guideline_indicated
            gray = False
            rationale = "leave-OE-out: independent guideline signal only"
        else:
            indicated = guideline_indicated and oe_indicated
            gray = guideline_indicated != oe_indicated  # ensemble disagreement
            rationale = "ensemble (guideline + OE) agreement" if not gray else "ensemble disagreement -> gray zone"

        # Fail closed: unknown/not-indicated tags are never independently indicated.
        if tag in {"not_independently_indicated", "unknown"}:
            indicated = False
            rationale = f"tag={tag}: not independently indicated (fail-closed)"

        return IndicationVerdict(
            action_id=action.action_id,
            judge_id=self.judge_id,
            judge_version=self.judge_version,
            independently_indicated=bool(indicated),
            gray_zone=bool(gray),
            rationale=rationale,
            leave_oe_out=self.leave_oe_out,
        )
