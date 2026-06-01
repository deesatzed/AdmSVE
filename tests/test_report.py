"""Combined report tests: three sections, silent stamp, doc-gap enrichment, no criteria leakage."""

from admission_engine.engine import AdmissionStatusEngine
from admission_engine.leakage_scan import CRITERIA_MARKERS
from admission_engine.report import SILENT_STAMP, build_corpus_report, render_report_html
from fixtures.generator import _doc_gap_case, _integrity_suppression_case, generate_corpus


def _build_report():
    engine = AdmissionStatusEngine()
    case_outputs, suppressions, traces, results = [], [], [], []
    rejected = []
    for case in generate_corpus(30):
        try:
            outcome = engine.run_case(case)
        except Exception as exc:
            rejected.append({"case_id": case.get("case_id"), "error": str(exc)})
            continue
        case_outputs.append(outcome.output.to_dict())
        traces.append({"case_id": outcome.case_id, "verified": outcome.trace.verify()[0]})
        suppressions.extend(s.__dict__ for s in outcome.gate_decision.suppressed)
    from admission_engine.metrics.harness import compute_metrics

    metrics = compute_metrics(results).to_dict()
    return build_corpus_report(
        metrics=metrics,
        case_outputs=case_outputs,
        suppressions=suppressions,
        rejected_cases=rejected,
        trace_verification=traces,
        version_pins={"engine_version": "test"},
        criteria_leakage_clean=True,
    )


def test_report_has_three_sections():
    report = _build_report()
    assert "section_1_analyst_metrics" in report
    assert "section_2_physician_advisor_cases" in report
    assert "section_3_compliance_provenance" in report


def test_report_is_stamped_silent_retrospective():
    report = _build_report()
    assert "SILENT RETROSPECTIVE VALIDATION" in report["stamp"]
    html = render_report_html(report)
    assert SILENT_STAMP in html
    assert "not for live UR use" in html.lower() or "not for live ur use" in html.lower()


def test_html_renders_all_three_section_headers():
    html = render_report_html(_build_report())
    assert "Section 1 — Analyst" in html
    assert "Section 2 — Physician-advisor" in html
    assert "Section 3 — Compliance" in html


def test_doc_gap_items_carry_evidence_and_strength():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_doc_gap_case(2))
    d = outcome.output.to_dict()
    assert d["documentation_gaps"], "expected doc gaps on a DOCGAP case"
    for item in d["documentation_gaps"]:
        assert "supporting_evidence" in item and isinstance(item["supporting_evidence"], list)
        assert item["strength"] in {"clear", "moderate", "borderline"}
    # Evidence must not be circular (must not point at the documentation_gaps field itself).
    for item in d["documentation_gaps"]:
        for ev in item["supporting_evidence"]:
            assert "current_visit.documentation_gaps" not in ev


def test_suppressed_action_appears_in_compliance_not_in_case_output():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_integrity_suppression_case(0))
    out = outcome.output.to_dict()
    # The trap must NOT appear anywhere in the surfaced tiered output.
    blob = str(out)
    assert "extend stay past a second midnight" not in blob
    # But it must be in the suppression log (compliance section source).
    assert any(s.action_id == "a-trap-1" for s in outcome.gate_decision.suppressed)


def test_rendered_html_has_no_criteria_text():
    html = render_report_html(_build_report()).lower()
    for marker in CRITERIA_MARKERS:
        assert marker not in html, f"criteria trademark '{marker}' leaked into rendered HTML"
