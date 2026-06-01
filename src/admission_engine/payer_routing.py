"""Payer routing: plan type selects the applicable standard and audit posture.

Plan type is the ROUTING KEY (handoff §3.1, Decision in §4). This module encodes ONLY the
public/regulatory layer — the CMS Two-Midnight rule and Inpatient-Only (IPO) list *concepts*.
It contains NO proprietary InterQual/MCG criteria text; the licensed-criteria conformance check
is a separate stubbed interface (see judges/criteria_interface.py).

Regulatory basis (cited in comments only; verify against CMS primary text before any real run):
- Traditional Medicare: Two-Midnight benchmark (≥2-midnight medically-necessary expectation,
  record-supported) + the two-midnight PRESUMPTION (2+ midnight stays presumed appropriate /
  audit-protected) + case-by-case exception + IPO list.
- Medicare Advantage (CMS-4201-F, eff. 2024-01-01): MA MUST follow the Two-Midnight rule,
  case-by-case exception, and IPO list — but the two-midnight PRESUMPTION does NOT apply, so MA
  may audit stays of any length; documentation must support the admission decision regardless of
  total time.
- Commercial / Medicaid: plan-specific; route to the applicable (future, licensed) criteria.
"""

from __future__ import annotations

from dataclasses import dataclass

PLAN_TYPES = {
    "traditional_medicare",
    "medicare_advantage",
    "commercial",
    "medicaid",
}


@dataclass(frozen=True)
class PayerRouting:
    plan_type: str
    applies_two_midnight_benchmark: bool
    applies_two_midnight_presumption: bool
    applies_case_by_case_exception: bool
    applies_ipo_list: bool
    may_audit_any_length: bool
    applicable_standard: str
    audit_posture: str
    regulatory_basis: str


def route(plan_type: str) -> PayerRouting:
    """Return the applicable standard + audit posture for a plan type."""
    pt = (plan_type or "").strip().lower()

    if pt == "traditional_medicare":
        return PayerRouting(
            plan_type=pt,
            applies_two_midnight_benchmark=True,
            applies_two_midnight_presumption=True,
            applies_case_by_case_exception=True,
            applies_ipo_list=True,
            may_audit_any_length=False,  # 2+ midnight stays are presumption-protected
            applicable_standard="cms_two_midnight_benchmark_with_presumption",
            audit_posture="presumption_protected_for_2plus_midnights",
            regulatory_basis="Two-Midnight benchmark + presumption + case-by-case exception + IPO list",
        )

    if pt == "medicare_advantage":
        return PayerRouting(
            plan_type=pt,
            applies_two_midnight_benchmark=True,
            applies_two_midnight_presumption=False,  # CMS-4201-F: presumption does NOT apply to MA
            applies_case_by_case_exception=True,
            applies_ipo_list=True,
            may_audit_any_length=True,
            applicable_standard="cms_two_midnight_benchmark_no_presumption",
            audit_posture="may_audit_any_length_documentation_must_support_decision",
            regulatory_basis="CMS-4201-F (eff 2024-01-01): Two-Midnight rule + exception + IPO; NO presumption",
        )

    if pt in {"commercial", "medicaid"}:
        return PayerRouting(
            plan_type=pt,
            applies_two_midnight_benchmark=False,
            applies_two_midnight_presumption=False,
            applies_case_by_case_exception=False,
            applies_ipo_list=False,
            may_audit_any_length=True,
            applicable_standard="plan_specific_route_to_applicable_criteria_stub",
            audit_posture="plan_specific",
            regulatory_basis="Plan-specific; route to applicable (future licensed) criteria",
        )

    raise ValueError(f"Unknown plan_type '{plan_type}'; expected one of {sorted(PLAN_TYPES)}")
