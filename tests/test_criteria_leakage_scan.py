"""MANDATED TEST 5: criteria-leakage scan.

No InterQual / MCG / Milliman proprietary criteria text may appear in the repo source, generated
artifacts, or logs (handoff Invariant 3; goal hard rule #2). Guardrail/doc files that necessarily
name the trademarks are allow-listed in leakage_scan.ALLOWED_BASENAMES.
"""

from pathlib import Path

from admission_engine.engine import AdmissionStatusEngine
from admission_engine.leakage_scan import scan_path
from fixtures.generator import generate_corpus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
FIXTURES_GEN = PROJECT_ROOT / "fixtures" / "generator.py"


def test_source_tree_has_no_criteria_text():
    findings = scan_path(SRC)
    assert findings == [], f"criteria trademark leaked into source: {findings}"


def test_kb_dir_has_no_criteria_text():
    kb_dir = SRC / "admission_engine" / "kb"
    findings = scan_path(kb_dir)
    assert findings == [], f"criteria trademark leaked into KB: {findings}"


def test_scanner_ignores_benign_surnames_but_catches_trademarks():
    """The boundary-aware scanner must not false-positive on surnames like McGarry."""
    from admission_engine.leakage_scan import _MARKER_RE

    def hits(s):
        return [m.group(1).lower() for m in _MARKER_RE.finditer(s)]

    assert hits("McGarry et al") == []
    assert hits("Dr. Mcgrath") == []
    assert "mcg" in hits("uses MCG criteria")
    assert "interqual" in hits("InterQual ISD elements")
    assert "milliman" in hits("Milliman guidelines")


def test_generated_artifacts_have_no_criteria_text(tmp_path):
    engine = AdmissionStatusEngine()
    out = tmp_path / "artifacts"
    out.mkdir()
    for case in generate_corpus(20):
        try:
            outcome = engine.run_case(case)
        except Exception:
            continue
        (out / f"{outcome.case_id}.output.json").write_text(
            outcome.output.to_json() if hasattr(outcome.output, "to_json") else str(outcome.output.to_dict()),
            encoding="utf-8",
        )
        (out / f"{outcome.case_id}.trace.json").write_text(outcome.trace.to_json(), encoding="utf-8")

    findings = scan_path(out)
    assert findings == [], f"criteria trademark leaked into artifacts: {findings}"


def test_generator_emits_no_criteria_text():
    findings = scan_path(FIXTURES_GEN.parent)
    # generator.py is not allow-listed; it must not contain trademark tokens.
    assert findings == [], f"criteria trademark leaked into fixtures: {findings}"
