"""Recommender abstraction (swappable port).

A real OpenEvidence + dotflows recommender is wired later behind this same ABC. The recommender
produces a candidate inpatient-likelihood and a list of candidate actions, each PROVENANCE-TAGGED,
captured verbatim before any judging (goal item 5).

PROVENANCE TAGS (handoff §3.4):
- criteria_derived          : derived from (licensed) status criteria
- rule_derived              : derived from public CMS rule logic
- clinically_indicated      : flagged by the OE/guideline layer as warranted regardless of billing
- documentation_of_existing_fact : captures necessity that already exists (no new care)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

PROVENANCE_TAGS = {
    "criteria_derived",
    "rule_derived",
    "clinically_indicated",
    "documentation_of_existing_fact",
}


@dataclass(frozen=True)
class RecommendedAction:
    action_id: str
    description: str
    provenance: str  # one of PROVENANCE_TAGS
    indication_tag: str  # from contracts.action_events.INDICATION_TAGS
    helps_status: bool  # does surfacing this help meet inpatient criteria?
    is_new_care: bool  # would surfacing this recommend NEW testing/treatment?
    rationale: str = ""


@dataclass(frozen=True)
class Recommendation:
    case_id: str
    recommender_id: str
    recommender_version: str
    inpatient_likelihood: float  # 0.0..1.0
    candidate_actions: list[RecommendedAction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None


class Recommender(ABC):
    """Swappable recommender port. Implementations must be deterministic for a given input in
    Phase 1 (no network, no nondeterminism) so reproducibility tests hold."""

    recommender_id: str = "abstract"
    recommender_version: str = "0"

    @abstractmethod
    def recommend(self, case_view: dict[str, Any]) -> Recommendation:
        """Produce a Recommendation from the recommender-visible case view only."""
        raise NotImplementedError
