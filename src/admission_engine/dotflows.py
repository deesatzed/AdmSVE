"""DotFlow registry: maps each engine role to its OpenEvidence DotFlow prompt + output schema.

The DotFlow markdown files in ``dotflows/`` are the human-authored OE prompts (the moat: workflow +
dotflows + validated data, per the handoff). In Phase 1 the recommender/judges run on deterministic
stubs; this registry pins the linkage so that, when the real OE recommender is wired behind
``recommender.base.Recommender``, each role loads its DotFlow and ingests the fenced JSON block whose
keys are declared here.

No proprietary criteria text lives in the DotFlows or here — the licensed-criteria conformance is
deferred to the stubbed criteria interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# dotflows/ sits at the project root (parent of src/).
DOTFLOWS_DIR = Path(__file__).resolve().parents[2] / "dotflows"


@dataclass(frozen=True)
class DotFlowSpec:
    role: str  # engine role this DotFlow serves
    filename: str  # markdown prompt under dotflows/
    output_schema: str  # the `schema` value the fenced JSON block must carry
    required_json_keys: tuple[str, ...] = field(default_factory=tuple)

    @property
    def path(self) -> Path:
        return DOTFLOWS_DIR / self.filename

    def exists(self) -> bool:
        return self.path.is_file()

    def text(self) -> str:
        return self.path.read_text(encoding="utf-8")


REGISTRY: dict[str, DotFlowSpec] = {
    "recommender": DotFlowSpec(
        role="recommender",
        filename="status_likelihood_recommender.md",
        output_schema="admission_engine.recommender_output.v0.1",
        required_json_keys=("case_id", "inpatient_likelihood", "candidate_actions"),
    ),
    "status_conformance": DotFlowSpec(
        role="status_conformance",
        filename="status_conformance_review.md",
        output_schema="admission_engine.status_conformance_output.v0.1",
        required_json_keys=(
            "case_id",
            "status_supports_inpatient",
            "documentation_gaps",
            "criteria_text_reproduced",
        ),
    ),
    "clinical_indication": DotFlowSpec(
        role="clinical_indication",
        filename="clinical_indication_review.md",
        output_schema="admission_engine.clinical_indication_output.v0.1",
        required_json_keys=("case_id", "verdicts"),
    ),
    "documentation_gap": DotFlowSpec(
        role="documentation_gap",
        filename="documentation_gap_capture.md",
        output_schema="admission_engine.documentation_gap_output.v0.1",
        required_json_keys=("case_id", "documentation_gaps", "new_care_proposed"),
    ),
    "denial_overturn": DotFlowSpec(
        role="denial_overturn",
        filename="denial_overturn_support.md",
        output_schema="admission_engine.denial_overturn_output.v0.1",
        required_json_keys=(
            "case_id",
            "denied_then_overturned",
            "surfaced_documentation_supported_overturn",
        ),
    ),
    "gap_analysis": DotFlowSpec(
        role="gap_analysis",
        filename="gap_analysis_review.md",
        output_schema="admission_engine.gap_analysis_output.v0.1",
        required_json_keys=("case_id", "condition_matched", "documentation_gaps", "new_care_proposed"),
    ),
}


def get(role: str) -> DotFlowSpec:
    if role not in REGISTRY:
        raise KeyError(f"Unknown DotFlow role '{role}'; known: {sorted(REGISTRY)}")
    return REGISTRY[role]


def all_specs() -> list[DotFlowSpec]:
    return list(REGISTRY.values())
