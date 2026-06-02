"""LLM-backed recommender — the app's default scoring backend.

Per the user's explicit choice, an LLM drives the candidate inpatient-likelihood and candidate
actions. It sits behind the EXISTING Recommender port, so engine.run_case wraps it with the SAME
deterministic integrity gate + tiered output. The FCA guardrail therefore stays enforced in CODE:
any candidate action that helps status but is not independently indicated is suppressed + logged by
integrity_gate/gate.py regardless of what the LLM proposed.

Two construction modes:
- from an already-parsed OE prose Recommendation (the normal app flow: OE did the reasoning, the
  LLM parsed it) — pass `prebuilt=`.
- from the case view directly (the LLM scores) — pass `llm=`; redacted/synthetic text only.

Determinism caveat: with a real LLM this path is non-deterministic. The deterministic
MockOpenEvidenceRecommender remains the default for the test harness; this backend is the app
default. Outputs carry the model id for audit.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..llm.base import LLMClient
from .base import Recommendation, RecommendedAction, Recommender

_SCORE_SYSTEM = (
    "You are a utilization-review scoring assistant. Given a decision-time case, estimate the "
    "likelihood (0..1) that the record supports INPATIENT level of service, and list candidate "
    "actions. For each action, state whether it is independently clinically indicated regardless of "
    "billing. NEVER recommend an action because it would help reach inpatient status. If the case is "
    "appropriately observation/outpatient, say so. Status accuracy, never status inflation."
)


class LLMRecommender(Recommender):
    recommender_id = "llm"

    def __init__(self, llm: LLMClient | None = None, prebuilt: Recommendation | None = None) -> None:
        self._llm = llm
        self._prebuilt = prebuilt
        self.recommender_version = (
            f"prebuilt::{prebuilt.recommender_version}" if prebuilt else f"llm::{getattr(llm, 'model', 'none')}"
        )

    def recommend(self, case_view: dict[str, Any]) -> Recommendation:
        if self._prebuilt is not None:
            # Normal app flow: OE reasoned, the prose parser built this. Re-stamp the case_id.
            p = self._prebuilt
            return Recommendation(
                case_id=case_view.get("case_id", p.case_id),
                recommender_id=self.recommender_id,
                recommender_version=self.recommender_version,
                inpatient_likelihood=p.inpatient_likelihood,
                candidate_actions=list(p.candidate_actions),
                notes=list(p.notes),
                raw=p.raw,
            )
        if self._llm is None:
            raise ValueError("LLMRecommender needs either prebuilt= or llm=")

        result = self._llm.complete(_score_prompt(case_view), system=_SCORE_SYSTEM)
        fields = _parse_score(result.text)
        likelihood = _clamp(fields.get("inpatient_likelihood", 0.5))
        actions = _to_actions(fields.get("candidate_actions", []))
        return Recommendation(
            case_id=case_view.get("case_id", ""),
            recommender_id=self.recommender_id,
            recommender_version=self.recommender_version,
            inpatient_likelihood=likelihood,
            candidate_actions=actions,
            notes=[f"llm_model={result.model}", f"prompt_hash={result.prompt_hash}"],
            raw={"provider": result.provider, "model": result.model},
        )


def _score_prompt(case_view: dict[str, Any]) -> str:
    cv = case_view.get("current_visit", {})
    return (
        f"Plan type: {case_view.get('plan_type','')}\n"
        f"Presenting problem: {case_view.get('presenting_problem','')}\n"
        f"Current-visit signals: {json.dumps(cv, sort_keys=True)}\n"
        f"Notes: {' '.join(case_view.get('notes', []))[:2000]}\n\n"
        "Return JSON: {\"inpatient_likelihood\": 0..1, \"candidate_actions\": "
        "[{\"description\": str, \"independently_indicated\": bool, \"helps_status\": bool}]}."
    )


def _parse_score(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _to_actions(items: list[dict[str, Any]]) -> list[RecommendedAction]:
    out: list[RecommendedAction] = []
    for i, it in enumerate(items or []):
        indicated = bool(it.get("independently_indicated", False))
        out.append(
            RecommendedAction(
                action_id=f"llm-{i:03d}",
                description=str(it.get("description", "")),
                provenance="clinically_indicated" if indicated else "criteria_derived",
                # The integrity gate independently re-judges this; the LLM's own tag does not bypass it.
                indication_tag="independently_indicated" if indicated else "not_independently_indicated",
                helps_status=bool(it.get("helps_status", False)),
                is_new_care=True,
                rationale="LLM-proposed; subject to the independent clinical-indication gate",
            )
        )
    return out


def _clamp(x: Any) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.5
