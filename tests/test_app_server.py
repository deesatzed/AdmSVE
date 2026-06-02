"""App server: endpoints via FastAPI TestClient on synthetic data, stub LLM. Redaction-before-LLM."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from admission_engine.app.server import create_app  # noqa: E402


def _client():
    return TestClient(create_app())


def test_health():
    r = _client().get("/health").json()
    assert r["ok"] is True
    assert "llm_provider" in r


def test_page_served():
    assert "<title>" in _client().get("/").text


def test_redact_endpoint_local():
    r = _client().post("/redact", json={"text": "SSN 123-45-6789 email a@b.com"}).json()
    assert "[SSN]" in r["redacted_text"]
    assert "[EMAIL]" in r["redacted_text"]
    assert "123-45-6789" not in r["redacted_text"]


def test_intake_redacts_before_llm_and_validates():
    body = {
        "text": "Patient John Smith COPD exacerbation hypercapnia BiPAP. SSN 123-45-6789",
        "payer": "Traditional Medicare",
        "plan_type": "traditional_medicare",
        "case_id": "CASE-1",
    }
    d = _client().post("/intake", json=body).json()
    assert d["valid"] is True
    assert "[SSN]" in d["oe_handoff"]["redacted_packet"]  # redacted before LLM
    assert d["oe_handoff"]["oe_dot_trigger"].startswith(".")
    assert d["use_limitation"]


def test_full_round_trip_prose_no_json():
    c = _client()
    intake = c.post(
        "/intake",
        json={"text": "COPD exacerbation, BiPAP, telemetry", "payer": "Traditional Medicare",
              "plan_type": "traditional_medicare", "case_id": "CASE-1"},
    ).json()
    prose = ("This patient requires inpatient hospital-level care; order serial blood gases and "
             "document oxygen requirement above baseline.")
    out = c.post("/ingest-oe", json={"case_snapshot": intake["case_snapshot"], "oe_prose": prose}).json()
    assert out["predicted_status"] in ("inpatient", "observation_or_outpatient")
    assert "documentation_gaps" in out["output"]
    assert out["oe_parse"]["status"] in ("parsed", "needs_review")
    assert out["oe_parse"]["raw_prose_hash"]
