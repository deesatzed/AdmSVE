"""MANDATED TEST 2: judge reproducibility from pinned version.

The same case run twice with the same pinned versions must produce byte-identical adjudication
(deterministic stubs, fixed clock). Version + criteria-version are snapshotted in the trace.
"""

from admission_engine.engine import AdmissionStatusEngine
from fixtures.generator import _inpatient_true_case, _doc_gap_case


def test_status_adjudication_is_byte_identical():
    engine = AdmissionStatusEngine()
    case = _inpatient_true_case(11)
    a = engine.run_case(case)
    b = engine.run_case(case)
    assert a.trace.to_json() == b.trace.to_json()
    assert a.output.to_dict() == b.output.to_dict()


def test_two_engine_instances_agree():
    case = _doc_gap_case(12)
    a = AdmissionStatusEngine().run_case(case)
    b = AdmissionStatusEngine().run_case(case)
    assert a.trace.to_json() == b.trace.to_json()


def test_trace_records_pinned_versions():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_inpatient_true_case(11))
    events = {e["event_type"]: e for e in outcome.trace.render()["events"]}
    adj = events["status_conformance_adjudication"]["data"]
    assert adj["criteria_version"]
    assert adj["cms_rule_effective_date"]
    assert events["case_loaded"]["data"]["engine_version"]
    # KB version is pinned in the trace alongside the engine/criteria versions.
    assert events["case_loaded"]["data"]["kb_version"] == "admission_engine.kb.v0.3"
    assert events["gap_analysis"]["data"]["kb_version"] == "admission_engine.kb.v0.3"


def test_trace_hash_chain_verifies():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_inpatient_true_case(11))
    ok, msg = outcome.trace.verify()
    assert ok, msg
