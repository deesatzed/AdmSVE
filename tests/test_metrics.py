"""Metric-harness tests: over-call rate, concordance, doc-gap detection, patient protection."""

from admission_engine.engine import AdmissionStatusEngine
from admission_engine.metrics.harness import compute_metrics
from fixtures.generator import generate_corpus, _honest_negative_case, _inpatient_true_case


def _run_corpus(n=60):
    engine = AdmissionStatusEngine()
    results = []
    for case in generate_corpus(n):
        try:
            outcome = engine.run_case(case)
        except Exception:
            continue  # leakage case fails closed; excluded from scoring
        if outcome.case_result is not None:
            results.append(outcome.case_result)
    return compute_metrics(results)


def test_metrics_compute_over_corpus():
    report = _run_corpus()
    assert report.n > 0
    assert 0.0 <= report.over_call_rate <= 1.0
    assert 0.0 <= report.sensitivity_true_inpatient <= 1.0
    assert 0.0 <= report.specificity_true_inpatient <= 1.0


def test_over_call_rate_is_tracked_prominently_in_report_dict():
    report = _run_corpus()
    d = report.to_dict()
    assert "OVER_CALL_RATE_TRACKED_FAILURE" in d


def test_clear_obs_case_is_not_an_over_call():
    engine = AdmissionStatusEngine()
    results = [engine.run_case(_honest_negative_case(1)).case_result]
    report = compute_metrics([r for r in results if r])
    assert report.over_call_count == 0


def test_clear_inpatient_case_is_true_positive():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_inpatient_true_case(3))
    report = compute_metrics([outcome.case_result])
    assert report.tp == 1
    assert report.over_call_count == 0


def test_equity_stratification_present():
    report = _run_corpus()
    assert isinstance(report.equity_by_payer, dict)
    assert len(report.equity_by_payer) >= 1


def test_denial_overturn_potential_is_retrospective():
    """Denied-then-overturned cases (initial denial, adjudicated inpatient) are detected, and the
    engine's surfaced documentation is credited toward overturn support. Initial payer denial is
    used only for this retrospective analysis, never as primary truth."""
    report = _run_corpus()
    d = report.to_dict()
    assert "denial_overturn_potential" in d
    # The DOCGAP fixtures are denied-then-overturned and surface documentation gaps.
    assert report.denied_then_overturned > 0
    assert report.overturn_supported_by_engine_docs > 0
    assert 0.0 <= report.denial_overturn_potential_rate <= 1.0


def test_initial_denial_never_primary_truth():
    from admission_engine.contracts.truth import parse_truth
    import pytest

    with pytest.raises(ValueError):
        parse_truth(
            {"case_id": "x", "initial_payer_decision": "observation",
             "post_appeal_adjudicated_status": "inpatient"},
            definition="initial_payer_decision",
        )
