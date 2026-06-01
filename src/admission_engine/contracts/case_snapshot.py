"""Case-snapshot input contract + leakage assertion.

Adapts EMEX's ``find_post_t0_leakage`` pattern (recursive dotted-path leakage scan) to the
admission-status domain. The recommender is only ever allowed to see the *decision-time*
information state. Validating "would have predicted status" on data that only existed
post-decision / post-adjudication / post-discharge is leakage (handoff Invariant 7); the run
must fail closed if any such field is present in the recommender-visible snapshot.

OPEN DECISION (surfaced, not resolved — see prereg/OPEN_DECISIONS.md):
  Decision-time information boundary = point-of-admission-decision vs full-encounter.
  Placeholder below is point-of-admission-decision. Change ``DECISION_TIME_BOUNDARY`` only via
  the pre-registration, not silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Placeholder for OPEN decision #3. Point-of-admission-decision is the conservative default:
# the engine may see history, presenting problem, current-visit data available at the admission
# decision, and current notes — but nothing produced after the admission decision is made.
DECISION_TIME_BOUNDARY = "point_of_admission_decision"  # OPEN: vs "full_encounter"

# Fields that, if present in the recommender-visible snapshot, constitute leakage. These are
# values that only exist AFTER the admission decision / AFTER adjudication / AFTER discharge.
# Truth (final adjudicated status) is held in a separate record and must never appear here.
FORBIDDEN_LEAKAGE_KEYS = {
    # adjudication / payer outcome (truth — must live only in the truth record)
    "final_adjudicated_status",
    "adjudicated_status",
    "payer_decision",
    "initial_payer_decision",
    "appeal_outcome",
    "post_appeal_status",
    "denial_reason",
    "overturn_result",
    # the admission decision itself (the thing being predicted)
    "admission_decision",
    "status_assigned",
    "billed_status",
    # post-decision / post-discharge encounter facts
    "actual_length_of_stay",
    "midnights_actually_crossed",
    "discharge_disposition",
    "post_discharge_outcome",
    "post_discharge_data",
    "readmission_30d",
    "ed_course_after_decision",
    "final_diagnosis",
}

REQUIRED_TOP_LEVEL = {
    "case_id",
    "mode",
    "payer",
    "plan_type",
    "presenting_problem",
    "current_visit",
    "history_comorbidities",
    "notes",
    "labs",
    "di_results",
    "actions",
}

# Keys carried alongside the snapshot for bookkeeping but NOT shown to the recommender.
# (Truth is parsed from its own record; this lets fixtures bundle truth in one file while the
# engine still enforces the separation by stripping these before the recommender sees anything.)
NON_RECOMMENDER_KEYS = {"truth", "_meta"}


@dataclass(frozen=True)
class CaseSnapshotValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]


def find_leakage(value: Any, prefix: str = "") -> list[str]:
    """Return dotted paths for any forbidden post-decision/adjudication/post-discharge fields.

    Recursive scan adapted from EMEX contracts.find_post_t0_leakage.
    """
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in FORBIDDEN_LEAKAGE_KEYS:
                paths.append(path)
            paths.extend(find_leakage(child, path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            paths.extend(find_leakage(child, f"{prefix}[{idx}]"))
    return paths


def recommender_visible_view(payload: dict[str, Any]) -> dict[str, Any]:
    """The strict subset of the case the recommender is allowed to see.

    Strips the truth record and any bookkeeping keys so leakage cannot enter via the
    recommender path even if a fixture bundles truth in the same file.
    """
    return {k: v for k, v in payload.items() if k not in NON_RECOMMENDER_KEYS}


def assert_no_leakage(payload: dict[str, Any]) -> None:
    """Fail closed if the recommender-visible snapshot contains any leakage field.

    Raises LeakageError — the run must abort rather than silently validate on future data.
    """
    view = recommender_visible_view(payload)
    leaked = find_leakage(view)
    if leaked:
        raise LeakageError(
            "Recommender-visible snapshot contains forbidden post-decision/adjudication fields: "
            + ", ".join(sorted(leaked))
        )


class LeakageError(Exception):
    """Raised when the decision-time information boundary is violated."""


def validate_case_snapshot(payload: dict[str, Any]) -> CaseSnapshotValidation:
    """Validate a synthetic case-snapshot input."""
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(REQUIRED_TOP_LEVEL - set(payload))
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")

    if payload.get("mode") != "synthetic":
        errors.append("Phase-1 runnable harness only accepts mode='synthetic'")

    if payload.get("source") == "real_ehr" or payload.get("source") == "real_claims":
        errors.append("Real EHR/claims data is blocked in Phase 1")

    if not payload.get("case_id"):
        errors.append("case_id must be non-empty")

    # Leakage check over the recommender-visible view.
    view = recommender_visible_view(payload)
    leaked = find_leakage(view)
    if leaked:
        errors.append(
            "Recommender-visible snapshot contains forbidden post-decision/adjudication fields: "
            + ", ".join(sorted(leaked))
        )

    actions = payload.get("actions")
    if actions is not None and not isinstance(actions, list):
        errors.append("actions must be a list")

    return CaseSnapshotValidation(valid=not errors, errors=errors, warnings=warnings)
