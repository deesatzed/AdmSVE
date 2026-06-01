"""Abstract port for licensed status criteria (InterQual / MCG / Milliman).

CRITICAL: This file and its implementations must NEVER embed, store, cache, paraphrase, or output
any proprietary criteria content. The real interface calls a LICENSED product/API. In Phase 1 the
only implementation is a STUB that returns a structured conformance verdict derived from the
synthetic case's own self-described fields — it contains no criteria text whatsoever.

OPEN DECISION (surfaced, not resolved — see prereg/OPEN_DECISIONS.md):
  InterQual vs MCG vs both for the future licensed interface. The port is abstract; no choice is
  baked in. ``criteria_product`` is a free-form label the future integration sets.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CriteriaConformance:
    case_id: str
    criteria_product: str  # e.g. future "interqual" | "mcg" — abstract here
    criteria_version: str  # pinned per case (handoff Invariant 6)
    meets_inpatient_criteria: bool
    # Documentation that would accurately reflect EXISTING necessity (no criteria text — these are
    # generic gap labels supplied by the case fixture, not proprietary content).
    documentation_gaps: list[str]
    confidence: float


class LicensedCriteriaInterface(ABC):
    criteria_product: str = "abstract"
    criteria_version: str = "0"

    @abstractmethod
    def evaluate(self, case_view: dict[str, Any]) -> CriteriaConformance:
        raise NotImplementedError


class StubbedCriteriaInterface(LicensedCriteriaInterface):
    """Phase-1 stub. Returns mock conformance from synthetic fields. NO proprietary criteria text."""

    criteria_product = "stubbed_licensed_criteria"  # placeholder; not InterQual/MCG
    criteria_version = "stub.v0.1"

    def evaluate(self, case_view: dict[str, Any]) -> CriteriaConformance:
        current = case_view.get("current_visit", {}) or {}
        # The synthetic fixture self-declares whether documented severity meets criteria. The stub
        # merely reads that scalar; it does not consult any licensed criteria content.
        meets = bool(current.get("synthetic_meets_inpatient_criteria", False))
        gaps = list(current.get("documentation_gaps", []) or [])
        confidence = float(current.get("criteria_confidence", 0.5))
        return CriteriaConformance(
            case_id=case_view.get("case_id", ""),
            criteria_product=self.criteria_product,
            criteria_version=self.criteria_version,
            meets_inpatient_criteria=meets,
            documentation_gaps=gaps,
            confidence=confidence,
        )
