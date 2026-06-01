"""Deterministic synthetic stand-in for the OpenEvidence + dotflows recommender.

NO network, NO randomness, NO real OE. Derives a candidate inpatient-likelihood and candidate
actions purely from the recommender-visible synthetic fields, so the same input always yields the
same output (required for judge-reproducibility and over-call accounting).

This is a STUB recommender for the synthetic phase. It does not embed any proprietary criteria;
it reads the synthetic case's own self-described severity/risk signals. The real OE recommender
replaces it behind recommender.base.Recommender.
"""

from __future__ import annotations

from typing import Any

from ..contracts.action_events import parse_action_events
from .base import PROVENANCE_TAGS, Recommendation, RecommendedAction, Recommender


class MockOpenEvidenceRecommender(Recommender):
    recommender_id = "mock_open_evidence"
    recommender_version = "stub.v0.1"

    def recommend(self, case_view: dict[str, Any]) -> Recommendation:
        case_id = case_view.get("case_id", "")
        current = case_view.get("current_visit", {}) or {}
        history = case_view.get("history_comorbidities", []) or []

        # Deterministic severity signal from the synthetic case's own self-reported fields.
        # These are synthetic scalars the fixture provides; no proprietary criteria are consulted.
        severity = float(current.get("severity_score", 0.0))  # 0..1 synthetic
        intensity = float(current.get("intensity_of_service_score", 0.0))  # 0..1 synthetic
        expected_midnights = float(current.get("expected_midnights", 0))  # synthetic clinician estimate
        comorbidity_burden = min(len(history) / 5.0, 1.0)

        # Simple deterministic blend -> likelihood that inpatient criteria are met.
        likelihood = _clamp(
            0.45 * severity
            + 0.25 * intensity
            + 0.20 * min(expected_midnights / 2.0, 1.0)
            + 0.10 * comorbidity_burden
        )

        candidate_actions = _build_candidate_actions(case_view)

        notes: list[str] = []
        if likelihood < 0.5:
            notes.append("Signals favor observation/outpatient; honest-negative output is appropriate.")

        return Recommendation(
            case_id=case_id,
            recommender_id=self.recommender_id,
            recommender_version=self.recommender_version,
            inpatient_likelihood=likelihood,
            candidate_actions=candidate_actions,
            notes=notes,
            raw={"severity": severity, "intensity": intensity, "expected_midnights": expected_midnights},
        )


def _build_candidate_actions(case_view: dict[str, Any]) -> list[RecommendedAction]:
    """Map the synthetic action list into provenance-tagged candidate actions.

    The recommender proposes candidates; the judges + integrity gate decide what may be surfaced.
    The recommender deliberately does NOT pre-filter on indication — that is the gate's job — so a
    'helps status only' action will appear here and must be suppressed downstream.
    """
    actions = parse_action_events(case_view.get("actions"))
    out: list[RecommendedAction] = []
    for a in actions:
        provenance = _provenance_for(a.indication_tag)
        helps_status = bool((a.raw or {}).get("helps_status", False))
        out.append(
            RecommendedAction(
                action_id=a.action_id,
                description=a.description,
                provenance=provenance,
                indication_tag=a.indication_tag,
                helps_status=helps_status,
                is_new_care=a.is_new_care,
                rationale=(a.raw or {}).get("rationale", ""),
            )
        )
    return out


def _provenance_for(indication_tag: str) -> str:
    mapping = {
        "documentation_of_existing_fact": "documentation_of_existing_fact",
        "independently_indicated": "clinically_indicated",
        "indicated_pending": "clinically_indicated",
        "not_independently_indicated": "criteria_derived",  # proposed only because it helps status
        "unknown": "rule_derived",
    }
    tag = mapping.get(indication_tag, "rule_derived")
    assert tag in PROVENANCE_TAGS
    return tag


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
