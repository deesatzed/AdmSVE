"""Metric harness over synthetic truth (handoff §3.5).

Hard-first / objective metrics:
- status concordance: predicted vs final adjudicated status (sensitivity/specificity for true inpatient)
- OVER-CALL RATE (critical safety/integrity metric): predicted inpatient that were truly
  observation/outpatient — the upcoding failure mode. Reported prominently; this is a tracked
  FAILURE, not a win.
- documentation-gap detection
- denial-overturn potential: on denied-then-overturned-to-inpatient cases, would the engine's
  surfaced documentation have supported the (later successful) appeal? (retrospective; §3.5)
- integrity-suppression count (proves the guardrail is live)
- calibration: stated likelihood vs realized adjudicated status
- patient-protection: truly-inpatient at risk of wrongful observation that the engine flagged
- equity stratification across payer/age/etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.truth import AdjudicatedTruth


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    predicted_status: str  # "inpatient" | "observation_or_outpatient"
    predicted_inpatient: bool
    inpatient_likelihood: float
    truth: AdjudicatedTruth
    suppression_count: int
    surfaced_doc_gap_count: int
    # equity strata
    payer: str = "unknown"
    plan_type: str = "unknown"
    age_band: str = "unknown"
    language: str = "unknown"
    race_ethnicity: str = "unknown"


@dataclass
class MetricReport:
    n: int
    # status concordance
    true_inpatient: int
    true_observation: int
    sensitivity_true_inpatient: float  # TP / (TP+FN)
    specificity_true_inpatient: float  # TN / (TN+FP)
    # over-call (THE tracked failure)
    over_call_count: int  # predicted inpatient but truly observation/outpatient
    over_call_rate: float  # over_call_count / predicted_inpatient_total
    # confusion
    tp: int
    fp: int
    tn: int
    fn: int
    # documentation gaps
    truly_inpatient_downgraded_for_docs: int
    doc_gaps_surfaced_on_those: int
    documentation_gap_detection_rate: float
    # denial-overturn potential (retrospective)
    denied_then_overturned: int
    overturn_supported_by_engine_docs: int
    denial_overturn_potential_rate: float
    # integrity
    total_integrity_suppressions: int
    # calibration (binned)
    calibration_bins: list[dict[str, Any]]
    # patient protection
    at_risk_wrongful_observation: int
    flagged_inpatient_among_at_risk: int
    patient_protection_rate: float
    # equity
    equity_by_payer: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "admission_engine.metrics.v0.1",
            "n": self.n,
            "OVER_CALL_RATE_TRACKED_FAILURE": round(self.over_call_rate, 4),
            "over_call_count": self.over_call_count,
            "status_concordance": {
                "true_inpatient": self.true_inpatient,
                "true_observation": self.true_observation,
                "sensitivity_true_inpatient": round(self.sensitivity_true_inpatient, 4),
                "specificity_true_inpatient": round(self.specificity_true_inpatient, 4),
                "confusion": {"tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn},
            },
            "documentation_gap_detection": {
                "truly_inpatient_downgraded_for_docs": self.truly_inpatient_downgraded_for_docs,
                "doc_gaps_surfaced_on_those": self.doc_gaps_surfaced_on_those,
                "detection_rate": round(self.documentation_gap_detection_rate, 4),
            },
            "denial_overturn_potential": {
                "denied_then_overturned": self.denied_then_overturned,
                "overturn_supported_by_engine_docs": self.overturn_supported_by_engine_docs,
                "potential_rate": round(self.denial_overturn_potential_rate, 4),
            },
            "integrity_suppression_count": self.total_integrity_suppressions,
            "calibration_bins": self.calibration_bins,
            "patient_protection": {
                "at_risk_wrongful_observation": self.at_risk_wrongful_observation,
                "flagged_inpatient_among_at_risk": self.flagged_inpatient_among_at_risk,
                "protection_rate": round(self.patient_protection_rate, 4),
            },
            "equity_by_payer": self.equity_by_payer,
        }


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def compute_metrics(results: list[CaseResult]) -> MetricReport:
    n = len(results)
    tp = fp = tn = fn = 0
    over_call = 0
    predicted_inpatient_total = 0
    true_inpatient = true_observation = 0
    downgraded = 0
    doc_gaps_on_downgraded = 0
    denied_overturned = 0
    overturn_supported = 0
    total_suppressions = 0
    at_risk = 0
    flagged_among_at_risk = 0

    for r in results:
        total_suppressions += r.suppression_count
        truth_inpatient = r.truth.true_inpatient
        true_inpatient += int(truth_inpatient)
        true_observation += int(not truth_inpatient)

        if r.predicted_inpatient:
            predicted_inpatient_total += 1
        if r.predicted_inpatient and truth_inpatient:
            tp += 1
        elif r.predicted_inpatient and not truth_inpatient:
            fp += 1
            over_call += 1  # predicted inpatient but truly observation/outpatient
        elif not r.predicted_inpatient and not truth_inpatient:
            tn += 1
        else:
            fn += 1

        if truth_inpatient and r.truth.downgraded_for_documentation:
            downgraded += 1
            if r.surfaced_doc_gap_count > 0:
                doc_gaps_on_downgraded += 1

        if truth_inpatient and r.truth.at_risk_wrongful_observation:
            at_risk += 1
            if r.predicted_inpatient:
                flagged_among_at_risk += 1

        # Denial-overturn potential (retrospective): on denied-then-overturned-to-inpatient cases,
        # would the engine's surfaced documentation have supported the (later successful) appeal?
        # Proxy: the engine predicted inpatient AND surfaced at least one documentation gap.
        if r.truth.denied_then_overturned:
            denied_overturned += 1
            if r.predicted_inpatient and r.surfaced_doc_gap_count > 0:
                overturn_supported += 1

    sensitivity = _safe_div(tp, tp + fn)
    specificity = _safe_div(tn, tn + fp)
    over_call_rate = _safe_div(over_call, predicted_inpatient_total)

    return MetricReport(
        n=n,
        true_inpatient=true_inpatient,
        true_observation=true_observation,
        sensitivity_true_inpatient=sensitivity,
        specificity_true_inpatient=specificity,
        over_call_count=over_call,
        over_call_rate=over_call_rate,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        truly_inpatient_downgraded_for_docs=downgraded,
        doc_gaps_surfaced_on_those=doc_gaps_on_downgraded,
        documentation_gap_detection_rate=_safe_div(doc_gaps_on_downgraded, downgraded),
        denied_then_overturned=denied_overturned,
        overturn_supported_by_engine_docs=overturn_supported,
        denial_overturn_potential_rate=_safe_div(overturn_supported, denied_overturned),
        total_integrity_suppressions=total_suppressions,
        calibration_bins=_calibration_bins(results),
        at_risk_wrongful_observation=at_risk,
        flagged_inpatient_among_at_risk=flagged_among_at_risk,
        patient_protection_rate=_safe_div(flagged_among_at_risk, at_risk),
        equity_by_payer=_equity_by_payer(results),
    )


def _calibration_bins(results: list[CaseResult], n_bins: int = 5) -> list[dict[str, Any]]:
    bins: list[dict[str, Any]] = []
    for b in range(n_bins):
        lo = b / n_bins
        hi = (b + 1) / n_bins
        members = [
            r for r in results
            if (lo <= r.inpatient_likelihood < hi) or (b == n_bins - 1 and r.inpatient_likelihood == 1.0)
        ]
        realized = _safe_div(sum(int(r.truth.true_inpatient) for r in members), len(members))
        mean_pred = _safe_div(sum(r.inpatient_likelihood for r in members), len(members))
        bins.append(
            {
                "bin": f"[{lo:.1f},{hi:.1f})",
                "count": len(members),
                "mean_predicted_likelihood": round(mean_pred, 4),
                "realized_true_inpatient_rate": round(realized, 4),
            }
        )
    return bins


def _equity_by_payer(results: list[CaseResult]) -> dict[str, dict[str, Any]]:
    by: dict[str, list[CaseResult]] = {}
    for r in results:
        by.setdefault(r.plan_type, []).append(r)
    out: dict[str, dict[str, Any]] = {}
    for plan_type, members in sorted(by.items()):
        pred_inp = sum(int(m.predicted_inpatient) for m in members)
        over = sum(int(m.predicted_inpatient and not m.truth.true_inpatient) for m in members)
        out[plan_type] = {
            "n": len(members),
            "predicted_inpatient": pred_inp,
            "over_call_count": over,
            "over_call_rate": round(_safe_div(over, pred_inp), 4),
        }
    return out
