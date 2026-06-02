"""Tiered, provenance-tagged output.

Tier 1 — Documentation gaps (highest value, lowest risk): necessity that likely already exists but
         is under-documented. NO new care.
Tier 2 — Already-indicated pending workup: clinically-indicated tests/treatments that will also
         clarify status — framed as "indicated anyway", never "do this to qualify".
Tier 3 — Honest negative: if it is and will remain observation/outpatient, say so.

Each item is tagged THREE ways so a reviewer can trust and act on it:
  - source_tag: the BASIS class (documentation_of_existing_fact / clinically_indicated / rule_derived / criteria_derived)
  - supporting_evidence: WHICH decision-time field in the case record backs the item (traceability)
  - strength: how strongly the record supports it (clear / moderate / borderline)

The engine must be willing to emit a Tier-3-only output (status accuracy, never status inflation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..integrity_gate.gate import GateDecision
from ..judges.status_conformance import StatusVerdict
from ..recommender.base import Recommendation

STRENGTH_CLEAR = "clear"
STRENGTH_MODERATE = "moderate"
STRENGTH_BORDERLINE = "borderline"


@dataclass(frozen=True)
class OutputItem:
    tier: int
    text: str
    source_tag: str  # criteria_derived | rule_derived | clinically_indicated | documentation_of_existing_fact
    basis: str
    supporting_evidence: list[str] = field(default_factory=list)  # decision-time fields backing this item
    strength: str = STRENGTH_MODERATE  # clear | moderate | borderline


@dataclass
class TieredOutput:
    case_id: str
    predicted_status: str  # "inpatient" | "observation_or_outpatient"
    inpatient_likelihood: float
    documentation_gaps: list[OutputItem] = field(default_factory=list)  # tier 1
    indicated_pending_workup: list[OutputItem] = field(default_factory=list)  # tier 2
    honest_negative: OutputItem | None = None  # tier 3
    use_limitation: str = (
        "Silent retrospective validation output. Not patient-facing, not orders, not a live status "
        "determination. Status accuracy, never status inflation."
    )

    def to_dict(self) -> dict[str, Any]:
        def item(i: OutputItem) -> dict[str, Any]:
            return {
                "tier": i.tier,
                "text": i.text,
                "source_tag": i.source_tag,
                "basis": i.basis,
                "supporting_evidence": list(i.supporting_evidence),
                "strength": i.strength,
            }

        return {
            "schema_version": "admission_engine.tiered_output.v0.2",
            "case_id": self.case_id,
            "predicted_status": self.predicted_status,
            "inpatient_likelihood": round(self.inpatient_likelihood, 4),
            "documentation_gaps": [item(i) for i in self.documentation_gaps],
            "indicated_pending_workup": [item(i) for i in self.indicated_pending_workup],
            "honest_negative": (item(self.honest_negative) if self.honest_negative else None),
            "use_limitation": self.use_limitation,
        }


# Predicted-status threshold. Conservative: only call inpatient when status support is affirmative.
INPATIENT_LIKELIHOOD_THRESHOLD = 0.5


def _strength_from_confidence(confidence: float) -> str:
    if confidence >= 0.8:
        return STRENGTH_CLEAR
    if confidence >= 0.55:
        return STRENGTH_MODERATE
    return STRENGTH_BORDERLINE


def _evidence_for_gap(gap_text: str, case_view: dict[str, Any]) -> list[str]:
    """Trace a documentation gap back to the decision-time fields that support it.

    Heuristic, decision-time-only: scans current_visit, notes, labs, di_results, and
    history_comorbidities for tokens that overlap the gap text. Never consults truth or any
    post-decision field (those are not in case_view).
    """
    evidence: list[str] = []
    gap_low = gap_text.lower()
    tokens = {w for w in _words(gap_low) if len(w) >= 4}

    def consider(label: str, value: Any) -> None:
        text = str(value).lower()
        if any(tok in text for tok in tokens):
            evidence.append(f"{label}: {value}")

    current = case_view.get("current_visit", {}) or {}
    for k, v in current.items():
        # Skip the gap-list field itself — matching a gap against the list of gaps is circular and
        # tells the reviewer nothing about WHERE in the chart the necessity is evidenced.
        if k == "documentation_gaps":
            continue
        consider(f"current_visit.{k}", v)
    for i, note in enumerate(case_view.get("notes", []) or []):
        consider(f"notes[{i}]", note)
    for i, lab in enumerate(case_view.get("labs", []) or []):
        consider(f"labs[{i}]", lab)
    for i, di in enumerate(case_view.get("di_results", []) or []):
        consider(f"di_results[{i}]", di)
    for i, hx in enumerate(case_view.get("history_comorbidities", []) or []):
        consider(f"history_comorbidities[{i}]", hx)

    if not evidence:
        evidence.append("record field not explicitly matched; reviewer must locate supporting fact in chart")
    return evidence


def _words(text: str) -> list[str]:
    return [w.strip(".,;:()[]") for w in text.replace("/", " ").split()]


def build_tiered_output(
    recommendation: Recommendation,
    status_verdict: StatusVerdict,
    gate_decision: GateDecision,
    case_view: dict[str, Any] | None = None,
    gap_items: list[OutputItem] | None = None,
) -> TieredOutput:
    case_view = case_view or {}
    case_id = recommendation.case_id

    # Predicted status combines the status judge's affirmative support with the recommender's
    # likelihood. Status accuracy: require the status judge to support inpatient AND likelihood>=thr.
    predicted_inpatient = (
        status_verdict.status_supports_inpatient
        and recommendation.inpatient_likelihood >= INPATIENT_LIKELIHOOD_THRESHOLD
    )
    predicted_status = "inpatient" if predicted_inpatient else "observation_or_outpatient"

    out = TieredOutput(
        case_id=case_id,
        predicted_status=predicted_status,
        inpatient_likelihood=recommendation.inpatient_likelihood,
    )

    criteria_strength = _strength_from_confidence(status_verdict.criteria.confidence)

    # Tier 1: documentation gaps from the status judge (existing necessity) + any surfaced
    # documentation-of-existing-fact actions.
    for gap in status_verdict.documentation_gaps:
        out.documentation_gaps.append(
            OutputItem(
                tier=1,
                text=f"Document existing necessity: {gap}",
                source_tag="documentation_of_existing_fact",
                basis="status-conformance documentation gap (existing fact)",
                supporting_evidence=_evidence_for_gap(gap, case_view),
                strength=criteria_strength,
            )
        )
    for action in gate_decision.surfaced:
        if action.provenance == "documentation_of_existing_fact":
            out.documentation_gaps.append(
                OutputItem(
                    tier=1,
                    text=action.description,
                    source_tag="documentation_of_existing_fact",
                    basis=action.rationale or "documentation of existing fact",
                    supporting_evidence=_evidence_for_gap(action.description, case_view),
                    strength=criteria_strength,
                )
            )

    # Tier 1 (cont.): KB-driven gap-analysis items. These are pre-built documentation-of-existing-fact
    # items; enforce the Tier-1 / no-new-care invariant on the way in (status accuracy, never inflation).
    for item in gap_items or []:
        if item.tier == 1 and item.source_tag == "documentation_of_existing_fact":
            out.documentation_gaps.append(item)

    # Tier 2: already-indicated pending workup (surfaced new-care actions that passed the gate).
    for action in gate_decision.surfaced:
        if action.provenance != "documentation_of_existing_fact" and action.is_new_care:
            out.indicated_pending_workup.append(
                OutputItem(
                    tier=2,
                    text=action.description,
                    source_tag=action.provenance,
                    basis=action.rationale or "independently clinically indicated (passed integrity gate)",
                    supporting_evidence=_evidence_for_gap(action.description, case_view),
                    strength=STRENGTH_CLEAR if action.provenance == "clinically_indicated" else STRENGTH_MODERATE,
                )
            )

    # Tier 3: honest negative when not predicted inpatient.
    if not predicted_inpatient:
        out.honest_negative = OutputItem(
            tier=3,
            text="This case appears appropriately observation/outpatient on the decision-time record.",
            source_tag="rule_derived",
            basis=f"status_supports_inpatient={status_verdict.status_supports_inpatient}; "
            f"likelihood={round(recommendation.inpatient_likelihood, 3)}",
            supporting_evidence=[
                f"inpatient_likelihood={round(recommendation.inpatient_likelihood, 3)}",
                f"meets_two_midnight_benchmark={status_verdict.meets_two_midnight_benchmark}",
            ],
            strength=_strength_from_confidence(status_verdict.criteria.confidence),
        )

    return out
