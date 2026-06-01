"""Status-conformance judge.

Answers: "does this meet inpatient criteria, and what is missing to DOCUMENT that it does?"
Combines the PUBLIC CMS rule logic (Two-Midnight / IPO concepts, via payer_routing) with a
STUBBED licensed-criteria interface (no proprietary text). Each adjudication is version-pinned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import CMS_RULE_EFFECTIVE_DATE
from ..payer_routing import route
from .criteria_interface import CriteriaConformance, LicensedCriteriaInterface, StubbedCriteriaInterface


@dataclass(frozen=True)
class StatusVerdict:
    case_id: str
    judge_id: str
    judge_version: str
    plan_type: str
    applicable_standard: str
    audit_posture: str
    cms_rule_effective_date: str
    # public-layer rule signal
    meets_two_midnight_benchmark: bool
    qualifies_case_by_case_exception: bool
    on_ipo_list: bool
    # licensed-criteria signal (stubbed)
    criteria: CriteriaConformance
    # combined
    status_supports_inpatient: bool
    documentation_gaps: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


class StatusConformanceJudge:
    judge_id = "status_conformance"
    judge_version = "v0.1"

    def __init__(self, criteria_interface: LicensedCriteriaInterface | None = None) -> None:
        self._criteria = criteria_interface or StubbedCriteriaInterface()

    def evaluate(self, case_view: dict[str, Any]) -> StatusVerdict:
        plan_type = case_view.get("plan_type", "")
        routing = route(plan_type)
        current = case_view.get("current_visit", {}) or {}

        # PUBLIC CMS layer (own logic; no proprietary criteria text).
        expected_midnights = float(current.get("expected_midnights", 0))
        meets_benchmark = (
            routing.applies_two_midnight_benchmark and expected_midnights >= 2.0
        )
        # Case-by-case exception: documented complex factors support a <2-midnight inpatient stay.
        qualifies_exception = (
            routing.applies_case_by_case_exception
            and bool(current.get("documented_complex_factors", False))
            and expected_midnights < 2.0
        )
        on_ipo = bool(current.get("on_inpatient_only_list", False)) and routing.applies_ipo_list

        criteria = self._criteria.evaluate(case_view)

        status_supports_inpatient = bool(
            meets_benchmark or qualifies_exception or on_ipo or criteria.meets_inpatient_criteria
        )

        rationale: list[str] = [
            f"plan_type={routing.plan_type}; standard={routing.applicable_standard}",
            f"two_midnight_presumption_applies={routing.applies_two_midnight_presumption}",
            f"may_audit_any_length={routing.may_audit_any_length}",
            f"expected_midnights={expected_midnights}",
        ]
        if on_ipo:
            rationale.append("on Inpatient-Only list (public concept)")

        return StatusVerdict(
            case_id=case_view.get("case_id", ""),
            judge_id=self.judge_id,
            judge_version=self.judge_version,
            plan_type=routing.plan_type,
            applicable_standard=routing.applicable_standard,
            audit_posture=routing.audit_posture,
            cms_rule_effective_date=CMS_RULE_EFFECTIVE_DATE,
            meets_two_midnight_benchmark=meets_benchmark,
            qualifies_case_by_case_exception=qualifies_exception,
            on_ipo_list=on_ipo,
            criteria=criteria,
            status_supports_inpatient=status_supports_inpatient,
            documentation_gaps=list(criteria.documentation_gaps),
            rationale=rationale,
        )
