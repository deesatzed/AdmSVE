"""Integrity gate implementation.

Rule (handoff Invariant 2): before the engine may surface any "new testing/new treatment" action,
that action must pass an INDEPENDENT clinical-indication check. Actions that pass only the
status-criteria check but fail the clinical-indication check are SUPPRESSED and LOGGED.

Decision table for a candidate action:
  - documentation_of_existing_fact (not new care)      -> SURFACE (Tier 1), no indication gate needed
  - new care AND independently_indicated               -> SURFACE (Tier 2)
  - new care AND NOT independently_indicated            -> SUPPRESS + LOG
  - new care AND gray_zone (ensemble disagreement)      -> SUPPRESS + LOG (fail closed) with gray flag
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..judges.clinical_indication import ClinicalIndicationJudge, IndicationVerdict
from ..recommender.base import RecommendedAction


@dataclass(frozen=True)
class SuppressionLogEntry:
    case_id: str
    action_id: str
    description: str
    reason: str
    helps_status: bool
    indication_tag: str
    gray_zone: bool


@dataclass
class GateDecision:
    case_id: str
    surfaced: list[RecommendedAction] = field(default_factory=list)
    suppressed: list[SuppressionLogEntry] = field(default_factory=list)
    verdicts: list[IndicationVerdict] = field(default_factory=list)

    @property
    def suppression_count(self) -> int:
        return len(self.suppressed)


class IntegrityGate:
    def __init__(self, indication_judge: ClinicalIndicationJudge | None = None) -> None:
        self._judge = indication_judge or ClinicalIndicationJudge()

    def filter_actions(
        self,
        case_view: dict[str, Any],
        candidate_actions: list[RecommendedAction],
    ) -> GateDecision:
        case_id = case_view.get("case_id", "")
        decision = GateDecision(case_id=case_id)

        for action in candidate_actions:
            # Tier-1 documentation of an existing fact is not new care; surface without a new-care gate.
            if not action.is_new_care:
                decision.surfaced.append(action)
                continue

            verdict = self._judge.evaluate(action, case_view)
            decision.verdicts.append(verdict)

            if verdict.gray_zone:
                decision.suppressed.append(
                    SuppressionLogEntry(
                        case_id=case_id,
                        action_id=action.action_id,
                        description=action.description,
                        reason="gray_zone_ensemble_disagreement_fail_closed",
                        helps_status=action.helps_status,
                        indication_tag=action.indication_tag,
                        gray_zone=True,
                    )
                )
                continue

            if verdict.independently_indicated:
                decision.surfaced.append(action)
            else:
                decision.suppressed.append(
                    SuppressionLogEntry(
                        case_id=case_id,
                        action_id=action.action_id,
                        description=action.description,
                        reason="status_helpful_but_not_independently_indicated",
                        helps_status=action.helps_status,
                        indication_tag=action.indication_tag,
                        gray_zone=False,
                    )
                )

        return decision
