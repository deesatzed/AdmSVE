"""Disease-library schema tests: 25 conditions, status-lever exclusion, new capability fields."""

import json
from pathlib import Path

from admission_engine.kb import (
    ConditionEntry,
    DocumentationPhrase,
    GapQuestion,
    KB_VERSION,
    load_kb,
)

CONDITIONS_DIR = Path(__file__).resolve().parents[1] / "src" / "admission_engine" / "kb" / "data" / "conditions"

EXPECTED_25 = {
    "acs_stemi", "adhf", "aki_ckd", "asthma", "cancer_ftt", "cellulitis", "cirrhosis", "copd",
    "delirium", "dementia_trigger", "diabetic_foot", "esrd_dialysis", "falls", "generalized_weakness",
    "gi_bleed", "htn_emergency", "hyperglycemia_dka", "hypoglycemia", "ibd_flare", "pneumonia",
    "seizure", "sickle_cell", "syncope", "tia", "uti_urosepsis",
}


def test_kb_version_bumped_to_v03():
    assert KB_VERSION == "admission_engine.kb.v0.3"
    assert load_kb().version == KB_VERSION


def test_all_25_conditions_load():
    kb = load_kb()
    assert {c.condition for c in kb.conditions} == EXPECTED_25
    assert len(kb.conditions) == 25


def test_recommended_status_and_confidence_excluded_from_schema():
    """Status levers must not exist in the schema (structural anti-inflation guarantee)."""
    fields = ConditionEntry.__dataclass_fields__
    assert "recommended_status" not in fields
    assert "confidence_level" not in fields


def test_recommended_status_absent_from_all_json():
    for path in CONDITIONS_DIR.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert "recommended_status" not in raw, path.name
        assert "confidence_level" not in raw, path.name


def test_condition_entry_has_new_capability_fields():
    fields = ConditionEntry.__dataclass_fields__
    for f in ("observation_features", "inpatient_features", "gap_questions", "documentation_phrases"):
        assert f in fields


def test_every_condition_and_doc_phrase_is_cited():
    kb = load_kb()
    for c in kb.conditions:
        assert c.citations, c.condition
        for dp in c.documentation_phrases:
            assert isinstance(dp, DocumentationPhrase)
            assert dp.citations, f"{c.condition} doc-phrase uncited"


def test_gap_question_shapes():
    kb = load_kb()
    classes = {"diagnostic_clarification", "treatment_escalation", "geriatric_safety", "documentation"}
    for c in kb.conditions:
        for q in c.gap_questions:
            assert isinstance(q, GapQuestion)
            assert q.question
            assert q.gap_class in classes
