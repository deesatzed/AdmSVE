"""LLM recommender path: the integrity gate STILL suppresses non-indicated actions (FCA guardrail).

This is the single most important safety test of the AI-enabled build: no matter what the LLM/OE
proposes, an action that helps status but is not independently indicated must be suppressed + logged.
"""

from admission_engine.engine import AdmissionStatusEngine
from admission_engine.recommender.base import Recommendation, RecommendedAction
from admission_engine.recommender.llm_recommender import LLMRecommender
from fixtures.generator import _honest_negative_case, _inpatient_true_case


def _rec_with(actions):
    return Recommendation(
        case_id="CASE-1",
        recommender_id="oe_prose",
        recommender_version="test",
        inpatient_likelihood=0.6,
        candidate_actions=actions,
    )


def test_integrity_gate_suppresses_non_indicated_llm_action():
    trap = RecommendedAction(
        action_id="trap",
        description="order observation labs to extend stay past a second midnight",
        provenance="criteria_derived",
        indication_tag="not_independently_indicated",
        helps_status=True,
        is_new_care=True,
        rationale="helps status only",
    )
    engine = AdmissionStatusEngine(recommender=LLMRecommender(prebuilt=_rec_with([trap])))
    outcome = engine.run_case(_honest_negative_case(1))
    suppressed = {s.action_id for s in outcome.gate_decision.suppressed}
    assert "trap" in suppressed
    assert "order observation labs" not in str(outcome.output.to_dict())


def test_independently_indicated_llm_action_passes():
    legit = RecommendedAction(
        action_id="legit",
        description="repeat troponin per ACS workup",
        provenance="clinically_indicated",
        indication_tag="independently_indicated",
        helps_status=False,
        is_new_care=True,
        rationale="standard workup",
    )
    case = _inpatient_true_case(2)
    case["actions"] = [
        {"action_id": "legit", "description": "repeat troponin per ACS workup",
         "clinical_indication_tag": "independently_indicated", "present": False,
         "guideline_indicated": True, "oe_indicated": True}
    ]
    engine = AdmissionStatusEngine(recommender=LLMRecommender(prebuilt=_rec_with([legit])))
    outcome = engine.run_case(case)
    surfaced = {a.action_id for a in outcome.gate_decision.surfaced}
    assert "legit" in surfaced


def test_llm_recommender_does_not_override_status_judge():
    """A high LLM likelihood cannot flip status when the record doesn't support inpatient."""
    rec = _rec_with([])
    rec = Recommendation(
        case_id="CASE-1", recommender_id="oe", recommender_version="t",
        inpatient_likelihood=0.99, candidate_actions=[],
    )
    engine = AdmissionStatusEngine(recommender=LLMRecommender(prebuilt=rec))
    outcome = engine.run_case(_honest_negative_case(1))
    # honest-negative case fields don't support inpatient -> status stays observation despite 0.99
    assert outcome.output.predicted_status == "observation_or_outpatient"
