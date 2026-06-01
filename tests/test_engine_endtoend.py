"""End-to-end engine test: full pipeline + tiered output + doc-gap surfacing + leave-OE-out."""

from admission_engine.engine import AdmissionStatusEngine
from fixtures.generator import _doc_gap_case, _inpatient_true_case


def test_doc_gap_case_surfaces_tier1_documentation():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_doc_gap_case(2))
    assert outcome.output.predicted_status == "inpatient"
    assert len(outcome.output.documentation_gaps) >= 1
    # All tier-1 items are documentation of existing fact (no new care).
    for item in outcome.output.documentation_gaps:
        assert item.tier == 1
        assert item.source_tag == "documentation_of_existing_fact"


def test_each_output_item_is_provenance_tagged():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_doc_gap_case(2))
    for item in outcome.output.documentation_gaps + outcome.output.indicated_pending_workup:
        assert item.source_tag


def test_leave_oe_out_sensitivity_runs():
    base = AdmissionStatusEngine(leave_oe_out=False).run_case(_inpatient_true_case(8))
    loo = AdmissionStatusEngine(leave_oe_out=True).run_case(_inpatient_true_case(8))
    # both produce a valid prediction; leave-OE-out is a recorded sensitivity mode.
    assert base.output.predicted_status in {"inpatient", "observation_or_outpatient"}
    assert loo.output.predicted_status in {"inpatient", "observation_or_outpatient"}


def test_outcome_serializes():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_inpatient_true_case(8))
    d = outcome.to_dict()
    assert d["case_id"]
    assert "output" in d and "trace" in d
