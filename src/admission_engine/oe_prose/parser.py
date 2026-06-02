"""Parse OpenEvidence PROSE into a Recommendation-shaped structure (no JSON).

Two layers, both fail-safe:
1. LLM layer: ask the configured LLM to read OE's prose and return the structured signals. Best
   effort; on stub / failure -> {}.
2. Deterministic layer: a conservative markdown/keyword reading that always yields *something*
   auditable, and marks the result `needs_review` when confidence is low.

The raw OE prose is always preserved verbatim and hashed for the audit trace. We never invent
candidate actions or a status that the prose does not support.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..hashing import hash_text
from ..llm.base import LLMClient
from ..recommender.base import Recommendation, RecommendedAction

_PARSE_SYSTEM = (
    "You convert an OpenEvidence clinical assessment (prose) into structured signals for a "
    "utilization-review engine. Extract only what the prose supports: an inpatient-likelihood (0..1), "
    "an honest observation/outpatient signal if stated, and any clearly clinically-indicated workup "
    "items the prose names. Do not invent items. Status accuracy, never status inflation."
)

# Phrases that signal an honest observation/outpatient reading.
_OBS_MARKERS = (
    "appropriately observation",
    "observation is appropriate",
    "outpatient is appropriate",
    "does not meet inpatient",
    "lower level of care",
    "suitable for observation",
)
_INPATIENT_MARKERS = (
    "supports inpatient",
    "meets inpatient",
    "requires inpatient",
    "hospital-level care",
    "inpatient admission is appropriate",
)


@dataclass
class ParsedOeOutput:
    recommendation: Recommendation
    raw_prose: str
    raw_prose_hash: str
    status: str  # "parsed" | "needs_review"
    parse_notes: list[str] = field(default_factory=list)
    llm_provider: str = "stub"
    llm_model: str = "deterministic-stub"


def parse_oe_prose(prose: str, *, case_id: str, llm: LLMClient) -> ParsedOeOutput:
    raw_hash = hash_text(prose)
    notes: list[str] = []

    llm_fields: dict[str, Any] = {}
    provider, model = "stub", "deterministic-stub"
    try:
        result = llm.complete(_parse_prompt(prose), system=_PARSE_SYSTEM)
        provider, model = result.provider, result.model
        llm_fields = _parse_llm_json(result.text)
    except Exception as exc:
        notes.append(f"LLM prose-parse unavailable; deterministic reading used ({exc})")

    det = _deterministic_read(prose)

    likelihood = _coalesce_float(llm_fields.get("inpatient_likelihood"), det["likelihood"])
    actions_src = llm_fields.get("indicated_workup") or det["indicated_workup"]
    candidate_actions = _to_actions(actions_src)

    # Confidence: needs_review when prose is too short / no markers / no structure recovered.
    low_confidence = len(prose.strip()) < 40 or (not det["has_marker"] and not llm_fields)
    status = "needs_review" if low_confidence else "parsed"
    if status == "needs_review":
        notes.append("Low parse confidence; raw OE prose preserved for clinician review.")

    rec = Recommendation(
        case_id=case_id,
        recommender_id="oe_prose",
        recommender_version=f"{provider}::{model}",
        inpatient_likelihood=likelihood,
        candidate_actions=candidate_actions,
        notes=[f"oe_prose_hash={raw_hash}"] + notes,
        raw={"oe_prose_hash": raw_hash, "status": status},
    )
    return ParsedOeOutput(
        recommendation=rec,
        raw_prose=prose,
        raw_prose_hash=raw_hash,
        status=status,
        parse_notes=notes,
        llm_provider=provider,
        llm_model=model,
    )


def _parse_prompt(prose: str) -> str:
    return (
        "OpenEvidence assessment (prose):\n\n"
        f"{prose}\n\n"
        "Return a JSON object: {\"inpatient_likelihood\": 0..1, "
        "\"indicated_workup\": [list of clearly-indicated workup item strings]}. "
        "Only what the prose supports; empty list if none."
    )


def _parse_llm_json(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return {k: data[k] for k in ("inpatient_likelihood", "indicated_workup") if k in data}


def _deterministic_read(prose: str) -> dict[str, Any]:
    low = prose.lower()
    obs = any(m in low for m in _OBS_MARKERS)
    inp = any(m in low for m in _INPATIENT_MARKERS)
    if obs and not inp:
        likelihood = 0.2
    elif inp and not obs:
        likelihood = 0.75
    else:
        likelihood = 0.5
    # Conservative workup extraction: bullet lines mentioning a test/treatment verb.
    workup = []
    for line in prose.splitlines():
        s = line.strip().lstrip("-*• ").strip()
        if s and re.search(r"\b(order|obtain|repeat|serial|consult|titrate|administer|trial)\b", s, re.I):
            workup.append(s[:160])
    return {"likelihood": likelihood, "indicated_workup": workup[:10], "has_marker": obs or inp}


def _to_actions(items: list[str]) -> list[RecommendedAction]:
    out: list[RecommendedAction] = []
    for i, desc in enumerate(items or []):
        out.append(
            RecommendedAction(
                action_id=f"oe-{i:03d}",
                description=str(desc),
                provenance="clinically_indicated",
                # Tagged as candidate-indicated; the integrity gate independently re-checks this.
                indication_tag="independently_indicated",
                helps_status=False,
                is_new_care=True,
                rationale="surfaced from OE prose; subject to the independent clinical-indication gate",
            )
        )
    return out


def _coalesce_float(a: Any, b: float) -> float:
    try:
        if a is not None:
            return max(0.0, min(1.0, float(a)))
    except (TypeError, ValueError):
        pass
    return b
