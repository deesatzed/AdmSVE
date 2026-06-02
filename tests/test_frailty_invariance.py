"""THE central guardrail: status-label invariance under frailty enrichment.

For any case C and any frailty fields F, engine(C) and engine(C+F) must yield byte-identical
predicted_status and inpatient_likelihood. Frailty may add Tier-1 documentation and gate-passed
Tier-2 actions and may raise patient protection, but it must NEVER move the status label or the
over-call rate. This is the anti-inflation guarantee (status accuracy, never status inflation).
"""

from admission_engine.engine import AdmissionStatusEngine
from admission_engine.judges.status_conformance import StatusConformanceJudge
from admission_engine.metrics.harness import compute_metrics
from admission_engine.recommender.mock_oe import MockOpenEvidenceRecommender
from admission_engine.contracts.case_snapshot import recommender_visible_view
from fixtures.generator import (
    DEFAULT_FRAILTY,
    _honest_negative_case,
    generate_corpus,
    with_frailty,
)

MAX_FRAILTY = {
    "cfs_score": 9,
    "adl_dependencies": 6,
    "cognitive_status": "severe_impairment",
    "social_support": "none",
    "recent_admissions": 5,
}


def test_frailty_does_not_change_predicted_status():
    engine = AdmissionStatusEngine()
    for case in generate_corpus(60):
        if "final_adjudicated_status" in str(case):
            continue  # planted leakage case fails closed
        base = engine.run_case(case)
        enriched = engine.run_case(with_frailty(case))
        assert base.output.predicted_status == enriched.output.predicted_status, case["case_id"]


def test_frailty_does_not_change_inpatient_likelihood():
    engine = AdmissionStatusEngine()
    for case in generate_corpus(60):
        if "final_adjudicated_status" in str(case):
            continue
        base = engine.run_case(case)
        enriched = engine.run_case(with_frailty(case))
        # Exact float equality — bytewise identical by construction or the test fails.
        assert base.output.inpatient_likelihood == enriched.output.inpatient_likelihood, case["case_id"]


def test_frailty_does_not_change_over_call_rate():
    engine = AdmissionStatusEngine()
    base_results, frailty_results = [], []
    for case in generate_corpus(60):
        try:
            b = engine.run_case(case)
            f = engine.run_case(with_frailty(case))
        except Exception:
            continue
        if b.case_result:
            base_results.append(b.case_result)
        if f.case_result:
            frailty_results.append(f.case_result)
    # Frailty must be NEUTRAL on over-call (stricter than <=).
    assert compute_metrics(frailty_results).over_call_rate == compute_metrics(base_results).over_call_rate


def test_adversarial_max_frailty_does_not_flip_observation_case():
    engine = AdmissionStatusEngine()
    base = engine.run_case(_honest_negative_case(1))
    enriched = engine.run_case(with_frailty(_honest_negative_case(1), MAX_FRAILTY))
    assert base.output.predicted_status == "observation_or_outpatient"
    assert enriched.output.predicted_status == "observation_or_outpatient"
    assert base.output.inpatient_likelihood == enriched.output.inpatient_likelihood


def test_frailty_fields_isolated_from_status_and_recommender():
    """Component-level proof: status judge + recommender ignore the frailty fields entirely."""
    base = recommender_visible_view(_honest_negative_case(1))
    enriched = recommender_visible_view(with_frailty(_honest_negative_case(1), MAX_FRAILTY))

    sj = StatusConformanceJudge()
    assert sj.evaluate(base).status_supports_inpatient == sj.evaluate(enriched).status_supports_inpatient
    assert sj.evaluate(base).meets_two_midnight_benchmark == sj.evaluate(enriched).meets_two_midnight_benchmark

    rec = MockOpenEvidenceRecommender()
    assert rec.recommend(base).inpatient_likelihood == rec.recommend(enriched).inpatient_likelihood


def test_frailty_raises_documentation_without_inflation():
    """Frailty adds documentation value (more Tier-1 gaps) while status stays put."""
    engine = AdmissionStatusEngine()
    base = engine.run_case(_honest_negative_case(1))
    enriched = engine.run_case(with_frailty(_honest_negative_case(1), DEFAULT_FRAILTY))
    assert len(enriched.output.documentation_gaps) > len(base.output.documentation_gaps)
    assert enriched.output.predicted_status == base.output.predicted_status
