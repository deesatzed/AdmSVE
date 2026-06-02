"""Intake extractor: redacted text -> valid case-snapshot; leakage firewall still applies."""

from admission_engine.intake import extract_case_snapshot
from admission_engine.llm import get_client
from admission_engine.contracts.case_snapshot import LeakageError, assert_no_leakage


def _stub():
    return get_client(force_stub=True)


def test_extracts_valid_snapshot():
    r = extract_case_snapshot(
        "COPD exacerbation with hypercapnia, BiPAP initiated, telemetry, serial blood gases",
        payer="Traditional Medicare",
        plan_type="traditional_medicare",
        case_id="CASE-1",
        llm=_stub(),
    )
    assert r.valid, r.errors
    assert r.case_snapshot["mode"] == "synthetic"
    assert r.case_snapshot["presenting_problem"]
    assert "current_visit" in r.case_snapshot


def test_snapshot_has_no_leakage():
    r = extract_case_snapshot(
        "syncope with injury, telemetry ordered",
        payer="MA Plan",
        plan_type="medicare_advantage",
        case_id="CASE-2",
        llm=_stub(),
    )
    # The extractor must never inject a post-decision/adjudication field.
    assert assert_no_leakage(r.case_snapshot) is None


def test_condition_recognized_from_text():
    r = extract_case_snapshot(
        "patient with decompensated heart failure and volume overload",
        payer="Medicaid",
        plan_type="medicaid",
        case_id="CASE-3",
        llm=_stub(),
    )
    assert r.case_snapshot["presenting_problem"] in ("adhf", "decompensated heart failure", "heart failure")
