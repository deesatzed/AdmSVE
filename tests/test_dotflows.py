"""DotFlow tests: presence, role-wiring, schema declaration, JSON contract, and leakage discipline."""

import re

from admission_engine import dotflows
from admission_engine.judges.clinical_indication import ClinicalIndicationJudge
from admission_engine.judges.status_conformance import StatusConformanceJudge
from admission_engine.leakage_scan import CRITERIA_MARKERS
from admission_engine.recommender.mock_oe import MockOpenEvidenceRecommender

EXPECTED_ROLES = {
    "recommender",
    "status_conformance",
    "clinical_indication",
    "documentation_gap",
    "denial_overturn",
    "gap_analysis",
}


def test_all_dotflow_files_exist():
    for spec in dotflows.all_specs():
        assert spec.exists(), f"missing DotFlow file: {spec.filename}"


def test_registry_covers_expected_roles():
    assert set(dotflows.REGISTRY) == EXPECTED_ROLES


def test_engine_components_reference_their_dotflow_role():
    assert MockOpenEvidenceRecommender.dotflow_role == "recommender"
    assert StatusConformanceJudge.dotflow_role == "status_conformance"
    assert ClinicalIndicationJudge.dotflow_role == "clinical_indication"
    for role in (
        MockOpenEvidenceRecommender.dotflow_role,
        StatusConformanceJudge.dotflow_role,
        ClinicalIndicationJudge.dotflow_role,
    ):
        assert dotflows.get(role).exists()


def test_each_dotflow_declares_its_output_schema_and_required_keys():
    for spec in dotflows.all_specs():
        text = spec.text()
        # The fenced JSON block must declare the role's schema string.
        assert spec.output_schema in text, f"{spec.filename} missing schema {spec.output_schema}"
        # Required contract keys must appear in the prompt's JSON block.
        for key in spec.required_json_keys:
            assert f'"{key}"' in text, f"{spec.filename} missing required JSON key '{key}'"


def test_each_dotflow_has_a_fenced_json_block():
    json_block = re.compile(r"```json\s*\{.*?\}\s*```", re.S)
    for spec in dotflows.all_specs():
        assert json_block.search(spec.text()), f"{spec.filename} has no fenced JSON block"


def test_no_proprietary_criteria_text_in_dotflows():
    for spec in dotflows.all_specs():
        low = spec.text().lower()
        for marker in CRITERIA_MARKERS:
            assert marker not in low, f"criteria trademark '{marker}' leaked into {spec.filename}"


def test_dotflows_enforce_decision_time_boundary():
    """Every DotFlow that takes the decision-time snapshot must instruct a leakage stop."""
    for role in ("recommender", "status_conformance", "documentation_gap", "gap_analysis"):
        text = dotflows.get(role).text().lower()
        assert "leakage" in text
        assert "post-decision" in text or "post-adjudication" in text or "post-discharge" in text


def test_dotflows_carry_anti_inflation_guardrail():
    """Core flows must forbid status-inflation framing."""
    for role in ("recommender", "documentation_gap", "gap_analysis"):
        text = dotflows.get(role).text().lower()
        assert "status accuracy, never status inflation" in text
