"""OE prose parser: prose -> Recommendation shape; raw preserved+hashed; needs_review on low conf."""

from admission_engine.llm import get_client
from admission_engine.oe_prose import parse_oe_prose


def _stub():
    return get_client(force_stub=True)


def test_parses_inpatient_prose():
    prose = (
        "This patient requires inpatient hospital-level care. Order serial blood gases and "
        "repeat troponin. Document the oxygen requirement above baseline."
    )
    out = parse_oe_prose(prose, case_id="C1", llm=_stub())
    assert out.status == "parsed"
    assert out.recommendation.inpatient_likelihood >= 0.5
    assert out.raw_prose == prose
    assert out.raw_prose_hash


def test_parses_observation_prose():
    prose = "This case appears appropriately observation; does not meet inpatient criteria today."
    out = parse_oe_prose(prose, case_id="C2", llm=_stub())
    assert out.recommendation.inpatient_likelihood < 0.5


def test_low_confidence_needs_review():
    out = parse_oe_prose("ok", case_id="C3", llm=_stub())
    assert out.status == "needs_review"  # too short to parse confidently
    assert out.raw_prose == "ok"  # raw still preserved, never fabricated


def test_raw_prose_always_hashed_for_audit():
    out = parse_oe_prose("Some assessment text that mentions inpatient care.", case_id="C4", llm=_stub())
    assert out.raw_prose_hash
    assert any("oe_prose_hash" in n for n in out.recommendation.notes)
