"""End-to-end engine: orchestrates one case through the Phase-1 pipeline.

Flow (silent, retrospective, synthetic):
  validate snapshot + assert no leakage
    -> recommender (swappable; mock OE in Phase 1) on the recommender-visible view
    -> status-conformance judge (public CMS logic + stubbed licensed criteria)
    -> integrity gate (independent clinical-indication judge) filters candidate actions
    -> tiered, provenance-tagged output
  every step snapshotted into a hash-chained trace with version + timestamp.

The engine NEVER sees the truth record when producing its prediction; truth is parsed separately
for scoring (metrics harness).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from . import CRITERIA_INTERFACE_VERSION, ENGINE_VERSION
from .kb import KB_VERSION
from .contracts.case_snapshot import (
    assert_no_leakage,
    recommender_visible_view,
    validate_case_snapshot,
)
from .contracts.truth import parse_truth
from .integrity_gate.gate import GateDecision, IntegrityGate
from .judges.clinical_indication import ClinicalIndicationJudge
from .judges.gap_analysis import GapAnalysisJudge
from .judges.status_conformance import StatusConformanceJudge
from .metrics.harness import CaseResult
from .output.tiered_output import TieredOutput, build_tiered_output
from .recommender.base import Recommender
from .recommender.mock_oe import MockOpenEvidenceRecommender
from .trace import Trace


@dataclass
class EngineOutcome:
    case_id: str
    output: TieredOutput
    gate_decision: GateDecision
    trace: Trace
    case_result: CaseResult | None  # None when no truth record is available

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "case_id": self.case_id,
            "output": self.output.to_dict(),
            "suppressed_actions": [s.__dict__ for s in self.gate_decision.suppressed],
            "trace": self.trace.render(),
        }
        return d


# Deterministic session id derived from the case id so corpus runs are byte-reproducible.
def _session_id_for(case_id: str) -> str:
    from .hashing import hash_text

    digest = hash_text("session:" + case_id)
    return str(UUID(digest[:32]))


# Fixed clock for deterministic traces in synthetic runs.
def _fixed_clock() -> Callable[[], str]:
    def clock() -> str:
        return "1970-01-01T00:00:00+00:00"

    return clock


class AdmissionStatusEngine:
    def __init__(
        self,
        recommender: Recommender | None = None,
        leave_oe_out: bool = False,
        deterministic_trace: bool = True,
        enable_gap_analysis: bool = True,
    ) -> None:
        self.recommender = recommender or MockOpenEvidenceRecommender()
        self.status_judge = StatusConformanceJudge()
        self.gate = IntegrityGate(ClinicalIndicationJudge(leave_oe_out=leave_oe_out))
        self.leave_oe_out = leave_oe_out
        self.deterministic_trace = deterministic_trace
        # KB-driven gap analysis. Flag exists so callers can A/B that it never inflates status.
        self.enable_gap_analysis = enable_gap_analysis
        self.gap_judge = GapAnalysisJudge() if enable_gap_analysis else None

    def run_case(self, payload: dict[str, Any]) -> EngineOutcome:
        case_id = payload.get("case_id", "")

        validation = validate_case_snapshot(payload)
        if not validation.valid:
            raise ValueError(f"Case {case_id} failed validation: {validation.errors}")

        # Fail closed on any decision-time leakage before the recommender sees anything.
        assert_no_leakage(payload)
        case_view = recommender_visible_view(payload)

        trace = Trace(
            session_id=_session_id_for(case_id),
            clock=_fixed_clock() if self.deterministic_trace else Trace.clock,
        )
        trace.add(
            "case_loaded",
            {
                "case_id": case_id,
                "engine_version": ENGINE_VERSION,
                "criteria_interface_version": CRITERIA_INTERFACE_VERSION,
                "kb_version": KB_VERSION,
                "leave_oe_out": self.leave_oe_out,
                "enable_gap_analysis": self.enable_gap_analysis,
                "plan_type": payload.get("plan_type", ""),
            },
        )

        recommendation = self.recommender.recommend(case_view)
        trace.add(
            "recommendation",
            {
                "recommender_id": recommendation.recommender_id,
                "recommender_version": recommendation.recommender_version,
                "inpatient_likelihood": recommendation.inpatient_likelihood,
                "candidate_action_ids": [a.action_id for a in recommendation.candidate_actions],
            },
        )

        status_verdict = self.status_judge.evaluate(case_view)
        trace.add(
            "status_conformance_adjudication",
            {
                "judge_id": status_verdict.judge_id,
                "judge_version": status_verdict.judge_version,
                "criteria_product": status_verdict.criteria.criteria_product,
                "criteria_version": status_verdict.criteria.criteria_version,
                "cms_rule_effective_date": status_verdict.cms_rule_effective_date,
                "status_supports_inpatient": status_verdict.status_supports_inpatient,
                "documentation_gaps": status_verdict.documentation_gaps,
            },
        )

        # KB-driven gap analysis (after status adjudication; documentation-of-existing-fact only).
        gap_items = []
        gap_seed_actions = []
        if self.gap_judge is not None:
            gap_verdict = self.gap_judge.evaluate(case_view)
            gap_items = gap_verdict.domain_gaps
            gap_seed_actions = gap_verdict.seed_actions
            trace.add(
                "gap_analysis",
                {
                    "judge_id": gap_verdict.judge_id,
                    "judge_version": gap_verdict.judge_version,
                    "kb_version": gap_verdict.kb_version,
                    "condition_matched": gap_verdict.condition_matched,
                    "domain_gap_count": len(gap_verdict.domain_gaps),
                    "seed_action_count": len(gap_seed_actions),
                    "honest_negative_signals": gap_verdict.honest_negative_signals,
                },
            )

        # Frailty-seeded Tier-2 actions join the recommender's candidates and pass through the SAME
        # integrity gate — no bypass. They cannot affect predicted status or likelihood.
        candidate_actions = list(recommendation.candidate_actions) + gap_seed_actions
        gate_decision = self.gate.filter_actions(case_view, candidate_actions)
        trace.add(
            "integrity_gate",
            {
                "surfaced_action_ids": [a.action_id for a in gate_decision.surfaced],
                "suppressed": [s.__dict__ for s in gate_decision.suppressed],
                "suppression_count": gate_decision.suppression_count,
            },
        )

        output = build_tiered_output(
            recommendation, status_verdict, gate_decision, case_view, gap_items=gap_items
        )
        trace.add(
            "tiered_output",
            {
                "predicted_status": output.predicted_status,
                "inpatient_likelihood": output.inpatient_likelihood,
                "doc_gap_count": len(output.documentation_gaps),
                "indicated_pending_count": len(output.indicated_pending_workup),
                "honest_negative": output.honest_negative is not None,
            },
        )

        case_result = self._score_if_truth(payload, output, gate_decision)
        return EngineOutcome(
            case_id=case_id,
            output=output,
            gate_decision=gate_decision,
            trace=trace,
            case_result=case_result,
        )

    def _score_if_truth(
        self, payload: dict[str, Any], output: TieredOutput, gate_decision: GateDecision
    ) -> CaseResult | None:
        truth_record = payload.get("truth")
        if not isinstance(truth_record, dict):
            return None
        truth = parse_truth({**truth_record, "case_id": payload.get("case_id", "")})
        meta = payload.get("_meta", {}) or {}
        predicted_inpatient = output.predicted_status == "inpatient"
        return CaseResult(
            case_id=payload.get("case_id", ""),
            predicted_status=output.predicted_status,
            predicted_inpatient=predicted_inpatient,
            inpatient_likelihood=output.inpatient_likelihood,
            truth=truth,
            suppression_count=gate_decision.suppression_count,
            surfaced_doc_gap_count=len(output.documentation_gaps),
            payer=payload.get("payer", "unknown"),
            plan_type=payload.get("plan_type", "unknown"),
            age_band=meta.get("age_band", "unknown"),
            language=meta.get("language", "unknown"),
            race_ethnicity=meta.get("race_ethnicity", "unknown"),
        )
