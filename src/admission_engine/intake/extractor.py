"""Free-text -> case-snapshot extractor (LLM-backed, deterministic-safe).

Given redacted clinical text plus a few clinician-supplied routing facts (payer/plan type), produce
a contract-valid case_snapshot. The LLM proposes structured current_visit signals from the prose;
a deterministic fallback (KB condition match + keyword scan) guarantees a valid snapshot even with
the stub LLM or on parse failure — so the app always runs and never fabricates a leakage field.

IMPORTANT: this maps prose to the engine's decision-time fields ONLY. It never invents a truth /
adjudicated status, and the resulting snapshot is validated by contracts.case_snapshot (which fails
closed on any post-decision leakage).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..contracts.case_snapshot import validate_case_snapshot
from ..kb import load_kb
from ..llm.base import LLMClient

_EXTRACT_SYSTEM = (
    "You are a clinical utilization-review intake assistant. From the decision-time clinical text, "
    "extract ONLY information available at the admission-decision moment. Never infer the final "
    "adjudicated status, length of stay, or any post-discharge outcome. Return your best reading of: "
    "presenting problem; expected midnights of medically necessary hospital care; whether documented "
    "complex factors support a short inpatient stay; key severity and intensity-of-service signals "
    "present in the record. Status accuracy, never status inflation."
)


@dataclass
class IntakeResult:
    case_snapshot: dict[str, Any]
    valid: bool
    errors: list[str] = field(default_factory=list)
    llm_provider: str = "stub"
    llm_model: str = "deterministic-stub"
    notes: list[str] = field(default_factory=list)


def extract_case_snapshot(
    redacted_text: str,
    *,
    payer: str,
    plan_type: str,
    case_id: str,
    llm: LLMClient,
    extra_fields: dict[str, Any] | None = None,
) -> IntakeResult:
    """Build a validated case_snapshot from redacted decision-time text."""
    notes: list[str] = []

    # 1) Ask the LLM for structured signals (best effort). On stub / parse failure -> {}.
    llm_fields: dict[str, Any] = {}
    try:
        result = llm.complete(_extract_prompt(redacted_text), system=_EXTRACT_SYSTEM)
        llm_fields = _parse_llm_fields(result.text)
        provider, model = result.provider, result.model
    except Exception as exc:  # fail-closed to deterministic path
        notes.append(f"LLM extraction unavailable; used deterministic fallback ({exc})")
        provider, model = "stub", "deterministic-stub"

    if not llm_fields:
        notes.append("Used deterministic fallback for current_visit signals.")

    # 2) Deterministic fallback / floor for every required signal (guarantees a runnable snapshot).
    current_visit = _deterministic_current_visit(redacted_text)
    current_visit.update({k: v for k, v in llm_fields.items() if v is not None})

    presenting = llm_fields.get("presenting_problem") or _deterministic_presenting(redacted_text)

    snapshot: dict[str, Any] = {
        "case_id": case_id,
        "mode": "synthetic",  # real mode is gated separately; intake produces synthetic-mode cases
        "source": "clinician_intake",
        "payer": payer,
        "plan_type": plan_type,
        "presenting_problem": presenting,
        "current_visit": current_visit,
        "history_comorbidities": _list_lines(redacted_text, ("history", "pmh", "comorbid")),
        "notes": [redacted_text] if redacted_text.strip() else [],
        "labs": _list_lines(redacted_text, ("lab", "troponin", "wbc", "creatinine", "lactate")),
        "di_results": _list_lines(redacted_text, ("ct", "x-ray", "xray", "imaging", "echo", "ultrasound")),
        "actions": [],
    }
    if extra_fields:
        snapshot.update(extra_fields)

    validation = validate_case_snapshot(snapshot)
    return IntakeResult(
        case_snapshot=snapshot,
        valid=validation.valid,
        errors=validation.errors,
        llm_provider=provider,
        llm_model=model,
        notes=notes,
    )


def _extract_prompt(text: str) -> str:
    return (
        "Decision-time clinical text (already redacted):\n\n"
        f"{text}\n\n"
        "Return a JSON object with keys: presenting_problem (string), expected_midnights (number), "
        "documented_complex_factors (boolean), severity_score (0..1), "
        "intensity_of_service_score (0..1). Only decision-time facts; no outcomes."
    )


def _parse_llm_fields(text: str) -> dict[str, Any]:
    """Best-effort JSON-object extraction from an LLM reply (the LLM edge may return prose+json)."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    allowed = {
        "presenting_problem",
        "expected_midnights",
        "documented_complex_factors",
        "severity_score",
        "intensity_of_service_score",
    }
    return {k: v for k, v in data.items() if k in allowed}


# --- deterministic fallback (KB + keyword scan; always produces valid signals) ---------------------

_SEVERITY_TOKENS = ("hypotension", "hypoxemia", "hypoxia", "altered", "delirium", "acidosis", "shock",
                    "unstable", "tachycardia", "sepsis", "troponin", "arrhythmia")
_INTENSITY_TOKENS = ("iv ", "intravenous", "telemetry", "bipap", "ventilation", "infusion", "drip",
                     "titration", "monitoring", "serial")


def _deterministic_current_visit(text: str) -> dict[str, Any]:
    low = text.lower()
    sev = min(sum(t in low for t in _SEVERITY_TOKENS) / 4.0, 1.0)
    inten = min(sum(t in low for t in _INTENSITY_TOKENS) / 4.0, 1.0)
    midnights = 2 if ("two midnight" in low or "2 midnight" in low or sev >= 0.75) else (1 if sev >= 0.4 else 0)
    return {
        "severity_score": round(sev, 3),
        "intensity_of_service_score": round(inten, 3),
        "expected_midnights": midnights,
        "documented_complex_factors": sev >= 0.5,
        "on_inpatient_only_list": False,
        "synthetic_meets_inpatient_criteria": sev >= 0.6 and inten >= 0.5,
        "criteria_confidence": 0.5,
        "documentation_gaps": [],
    }


def _deterministic_presenting(text: str) -> str:
    kb = load_kb()
    cond = kb.condition_for(text)
    if cond is not None:
        return cond.condition.replace("_", " ")
    first = text.strip().splitlines()[0] if text.strip() else "unspecified presenting problem"
    return first[:120]


def _list_lines(text: str, keywords: tuple[str, ...]) -> list[str]:
    out = []
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in keywords) and line.strip():
            out.append(line.strip())
    return out[:20]
