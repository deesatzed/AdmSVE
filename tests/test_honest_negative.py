"""MANDATED TEST 4: willingness to say "observation/outpatient".

The engine must be able to output an honest negative and must NOT over-call inpatient on a clearly
observation case (status accuracy, never status inflation; goal hard rule #4).
"""

from admission_engine.engine import AdmissionStatusEngine
from fixtures.generator import _honest_negative_case


def test_engine_outputs_observation_on_clear_obs_case():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_honest_negative_case(1))
    assert outcome.output.predicted_status == "observation_or_outpatient"
    assert outcome.output.honest_negative is not None
    assert outcome.output.honest_negative.tier == 3


def test_engine_does_not_overcall_clear_obs_case():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_honest_negative_case(1))
    assert outcome.output.predicted_status != "inpatient"
    assert outcome.case_result is not None
    # truth is observation -> predicting observation is NOT an over-call.
    assert outcome.case_result.truth.true_inpatient is False
    assert outcome.case_result.predicted_inpatient is False
