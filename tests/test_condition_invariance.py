"""Status-label invariance under disease-condition enrichment (the anti-inflation guarantee).

Enriching a case so it matches a disease-condition pack may add Tier-1 documentation items and
honest-negative signals, but must NEVER change predicted_status or inpatient_likelihood.
"""

from admission_engine.engine import AdmissionStatusEngine
from admission_engine.judges.gap_analysis import GapAnalysisJudge
from admission_engine.contracts.case_snapshot import recommender_visible_view
from admission_engine.kb import load_kb
from fixtures.generator import condition_case, condition_obs_case, _honest_negative_case

# One representative presenting-problem string per condition slug (matches aliases).
CONDITION_PROBES = {
    "copd": "copd exacerbation",
    "asthma": "asthma exacerbation",
    "pneumonia": "pneumonia",
    "esrd_dialysis": "dialysis complication",
    "uti_urosepsis": "urosepsis",
    "cellulitis": "cellulitis",
    "diabetic_foot": "diabetic foot infection",
    "hyperglycemia_dka": "diabetic ketoacidosis",
    "hypoglycemia": "hypoglycemia",
    "aki_ckd": "acute kidney injury",
    "htn_emergency": "hypertensive emergency",
    "tia": "transient ischemic attack",
    "seizure": "breakthrough seizure",
    "gi_bleed": "gastrointestinal bleed",
    "cirrhosis": "decompensated cirrhosis",
    "ibd_flare": "ibd flare",
    "sickle_cell": "sickle cell crisis",
    "cancer_ftt": "febrile neutropenia",
    "falls": "fall with injury",
    "delirium": "altered mental status",
    "dementia_trigger": "dementia with trigger",
    "generalized_weakness": "generalized weakness",
}


def test_all_probes_match_a_condition():
    kb = load_kb()
    for slug, problem in CONDITION_PROBES.items():
        assert kb.condition_for(problem) is not None, f"{problem!r} should match a condition"


def test_condition_enrichment_does_not_change_predicted_status():
    engine = AdmissionStatusEngine()
    for idx, (slug, problem) in enumerate(CONDITION_PROBES.items()):
        base = engine.run_case(_honest_negative_case(idx))
        enriched = engine.run_case(condition_case(idx, problem, "clinical note with intravenous therapy and oxygen"))
        assert base.output.predicted_status == enriched.output.predicted_status, slug


def test_condition_enrichment_does_not_change_inpatient_likelihood():
    """A/B the gap-analysis flag on a matched case: status + likelihood must be byte-identical."""
    for idx, (slug, problem) in enumerate(CONDITION_PROBES.items()):
        case = condition_case(idx, problem, "intravenous antibiotics, telemetry, serial labs")
        on = AdmissionStatusEngine(enable_gap_analysis=True).run_case(case)
        off = AdmissionStatusEngine(enable_gap_analysis=False).run_case(case)
        assert on.output.inpatient_likelihood == off.output.inpatient_likelihood, slug
        assert on.output.predicted_status == off.output.predicted_status, slug


def test_condition_fields_isolated_from_status_and_recommender():
    from admission_engine.judges.status_conformance import StatusConformanceJudge
    from admission_engine.recommender.mock_oe import MockOpenEvidenceRecommender

    plain = recommender_visible_view(_honest_negative_case(1))
    matched = recommender_visible_view(condition_case(1, "copd exacerbation", "bipap hypercapnia"))
    sj = StatusConformanceJudge()
    assert sj.evaluate(plain).status_supports_inpatient == sj.evaluate(matched).status_supports_inpatient
    rec = MockOpenEvidenceRecommender()
    assert rec.recommend(plain).inpatient_likelihood == rec.recommend(matched).inpatient_likelihood


def test_gap_questions_are_tier1_documentation():
    v = GapAnalysisJudge().evaluate(recommender_visible_view(condition_case(1, "copd exacerbation", "bipap")))
    gq = [i for i in v.domain_gaps if "gap-question" in i.basis]
    assert gq, "expected gap-question items on a matched condition"
    for i in gq:
        assert i.tier == 1
        assert i.source_tag == "documentation_of_existing_fact"
    # gap-questions never become seed (new-care) actions
    assert all(not a.action_id.startswith("gapq") for a in v.seed_actions)


def test_doc_phrase_with_evidence_is_surfaced():
    v = GapAnalysisJudge().evaluate(
        recommender_visible_view(condition_case(1, "copd exacerbation", "bipap hypercapnia oxygen acidosis"))
    )
    dp = [i for i in v.domain_gaps if "doc-phrase" in i.basis]
    assert dp, "doc-phrase should surface when evidence tokens overlap"
    for i in dp:
        assert i.supporting_evidence  # traceable, no fabrication


def test_doc_phrase_without_evidence_not_surfaced():
    v = GapAnalysisJudge().evaluate(
        recommender_visible_view(condition_case(2, "copd exacerbation", "patient comfortable no distress"))
    )
    dp = [i for i in v.domain_gaps if "doc-phrase" in i.basis]
    assert dp == [], "doc-phrase must be suppressed without evidentiary overlap (no fabrication)"


def test_observation_features_feed_honest_negative():
    # Asthma obs features ("rapid symptom improvement", "safe home action plan") share no tokens
    # with its inpatient features ("recurrent bronchodilator need", "intravenous magnesium").
    v = GapAnalysisJudge().evaluate(
        recommender_visible_view(
            condition_obs_case(1, "asthma exacerbation", "rapid symptom improvement with safe home action plan in place")
        )
    )
    assert any(s.startswith("condition_observation_lean:") for s in v.honest_negative_signals)


def test_high_inflation_modules_social_content_not_tier1():
    """Weakness/dementia/falls/delirium: social content must not be standalone Tier-1 necessity."""
    engine = AdmissionStatusEngine()
    for idx, problem in enumerate(["generalized weakness", "dementia with trigger", "fall with injury", "altered mental status"]):
        case = condition_case(idx, problem)
        case["current_visit"]["social_support"] = "none"  # no care_delivery_barrier_documented
        out = engine.run_case(case)
        social_t1 = [g for g in out.output.documentation_gaps if "social_support" in g.basis]
        assert social_t1 == [], f"{problem}: social content must not be Tier-1 without care linkage"


def test_no_duplicate_gap_items():
    v = GapAnalysisJudge().evaluate(recommender_visible_view(condition_case(1, "copd exacerbation", "bipap hypercapnia")))
    texts = [i.text for i in v.domain_gaps]
    assert len(texts) == len(set(texts)), "no duplicate Tier-1 items"
