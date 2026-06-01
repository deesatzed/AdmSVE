"""Adjudicated-status truth schema.

This is the FOUNDATION of the validity claim (handoff §3.1) and is an OPEN decision:
which adjudicated status counts as "truth"?

OPEN DECISION (surfaced, not resolved — see prereg/OPEN_DECISIONS.md):
  candidates = final UR/physician-advisor determination | post-appeal adjudicated status |
  payer decision. The placeholder below favors the POST-APPEAL ADJUDICATED status and
  explicitly refuses to treat the INITIAL PAYER DENIAL as primary truth, because initial
  payer decisions are adversarial and themselves often wrong (handoff caution). The human
  must confirm or change ``TRUTH_DEFINITION_PLACEHOLDER`` via the pre-registration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# OPEN decision #1 placeholder. Do not silently change.
TRUTH_DEFINITION_PLACEHOLDER = "post_appeal_adjudicated_status"

VALID_STATUSES = {"inpatient", "observation", "outpatient"}

# Candidate truth sources a fixture may carry; the active one is selected by
# TRUTH_DEFINITION_PLACEHOLDER. Initial payer denial is recorded for analysis but is NOT
# permitted as primary truth.
TRUTH_SOURCE_FIELDS = {
    "post_appeal_adjudicated_status",
    "ur_physician_advisor_determination",
    "initial_payer_decision",  # recorded only; NEVER primary truth
}


@dataclass(frozen=True)
class AdjudicatedTruth:
    case_id: str
    final_status: str  # one of VALID_STATUSES, per the selected truth definition
    truth_source: str  # which field was used (the placeholder definition)
    true_inpatient: bool
    # context for metrics (not seen by recommender)
    downgraded_for_documentation: bool = False  # truly inpatient but denied/downgraded for doc reasons
    at_risk_wrongful_observation: bool = False  # truly inpatient, exposed to wrongful obs cost-sharing/SNF loss
    # Retrospective-only: the initial payer decision (recorded for analysis, NEVER primary truth) and
    # whether this case was denied-then-overturned to inpatient (denial-overturn-potential metric, §3.5).
    initial_payer_decision: str | None = None
    denied_then_overturned: bool = False
    raw: dict[str, Any] | None = None


def parse_truth(record: dict[str, Any], definition: str = TRUTH_DEFINITION_PLACEHOLDER) -> AdjudicatedTruth:
    """Parse a truth record using the (placeholder) truth definition.

    Refuses to use the initial payer denial as primary truth.
    """
    if definition == "initial_payer_decision":
        raise ValueError(
            "Initial payer decision must NOT be used as primary truth (handoff §3.1 caution). "
            "Use post_appeal_adjudicated_status or ur_physician_advisor_determination."
        )

    final_status = record.get(definition)
    if final_status is None:
        raise ValueError(f"Truth record missing the configured truth field '{definition}'")
    if final_status not in VALID_STATUSES:
        raise ValueError(f"Invalid truth status '{final_status}'; expected one of {sorted(VALID_STATUSES)}")

    initial = record.get("initial_payer_decision")
    # Denied-then-overturned: initial payer decision was NOT inpatient, but the adjudicated truth is.
    # This is the retrospective denial-overturn-potential cohort (handoff §3.5).
    denied_then_overturned = (
        final_status == "inpatient" and initial is not None and initial != "inpatient"
    )

    return AdjudicatedTruth(
        case_id=record.get("case_id", ""),
        final_status=final_status,
        truth_source=definition,
        true_inpatient=(final_status == "inpatient"),
        downgraded_for_documentation=bool(record.get("downgraded_for_documentation", False)),
        at_risk_wrongful_observation=bool(record.get("at_risk_wrongful_observation", False)),
        initial_payer_decision=initial,
        denied_then_overturned=denied_then_overturned,
        raw=record,
    )
