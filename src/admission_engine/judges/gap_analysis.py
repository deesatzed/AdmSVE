"""Gap-analysis judge — the knowledge-base-driven documentation-gap surfacer.

Realizes the central thesis of the ingested research: the high-value product is an EXPLAINABLE GAP
ANALYSIS, not a binary admit/observe classifier. For a borderline case it asks, per domain, "what
existing necessity is present in the decision-time record but under-documented?" and emits Tier-1
``documentation_of_existing_fact`` items only.

HARD INVARIANTS (status accuracy, never status inflation):
- This judge NEVER asserts a status label and NEVER proposes new care. Every item it emits is
  Tier-1 documentation of an EXISTING fact. New care stays routed through the integrity gate.
- It reads ONLY the decision-time ``case_view`` (no truth / post-decision fields).
- It is deterministic: KB iterated in stable load order; matched fields sorted.

Knowledge comes from the citation-tagged KB (admission_engine.kb): the six gap domains and, when the
presenting problem matches, a condition pack's inpatient-escalation signals. No proprietary
criteria text is consulted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..kb import KB_VERSION, FrailtySignal, GapDomain, KnowledgeBase, load_kb
from ..output.tiered_output import (
    STRENGTH_BORDERLINE,
    STRENGTH_CLEAR,
    STRENGTH_MODERATE,
    OutputItem,
)
from ..recommender.base import RecommendedAction


@dataclass(frozen=True)
class GapAnalysisVerdict:
    case_id: str
    judge_id: str
    judge_version: str
    kb_version: str
    condition_matched: str | None
    domain_gaps: list[OutputItem] = field(default_factory=list)  # Tier-1 documentation-of-existing-fact
    honest_negative_signals: list[str] = field(default_factory=list)  # domains where clue is ABSENT
    rationale: list[str] = field(default_factory=list)
    # Tier-2 candidate actions seeded by frailty signals. These do NOT bypass the integrity gate —
    # the engine appends them to the recommender's candidate actions and they must pass the gate.
    seed_actions: list[RecommendedAction] = field(default_factory=list)


# Decision-time fields a frailty signal may read. All are point-of-admission facts (no leakage).
_FRAILTY_FIELDS = ("cfs_score", "adl_dependencies", "cognitive_status", "social_support", "recent_admissions")


# Fields of the decision-time view scanned for already-present-but-undocumented necessity.
_SCANNED_FIELDS = ("current_visit", "notes", "labs", "di_results", "history_comorbidities")


class GapAnalysisJudge:
    judge_id = "gap_analysis"
    judge_version = "v0.1"
    # Backed by dotflows/gap_analysis_review.md (KB-driven gap surfacing; no proprietary criteria).
    dotflow_role = "gap_analysis"

    def __init__(self, kb: KnowledgeBase | None = None) -> None:
        self._kb = kb or load_kb()

    def evaluate(self, case_view: dict[str, Any]) -> GapAnalysisVerdict:
        case_id = case_view.get("case_id", "")
        condition = self._kb.condition_for(case_view.get("presenting_problem", ""))
        haystack = _haystack(case_view)
        already_documented = _already_documented(case_view)

        domain_gaps: list[OutputItem] = []
        honest_negative_signals: list[str] = []
        rationale: list[str] = []

        if condition is not None:
            rationale.append(f"matched condition pack: {condition.condition}")

        for domain in self._kb.gap_domains:  # stable KB load order -> deterministic
            clues = list(domain.inpatient_escalation_clues)
            # If the condition is matched, fold in its SI/IS escalation signals for this gap pass.
            if condition is not None:
                clues = clues + list(condition.si_thresholds) + list(condition.is_requirements)

            matched_fields = _matched_fields(case_view, clues)
            if matched_fields and not _gap_already_captured(domain, already_documented):
                # Present-but-undocumented existing necessity -> a Tier-1 documentation gap.
                cite = domain.citations[0].ref_id if domain.citations else ""
                domain_gaps.append(
                    OutputItem(
                        tier=1,
                        text=f"Document existing necessity ({domain.domain}): {domain.typical_documentation_gap}",
                        source_tag="documentation_of_existing_fact",
                        basis=f"gap-analysis domain '{domain.domain}' (existing fact; KB cite {cite})",
                        supporting_evidence=matched_fields,
                        strength=_strength(len(matched_fields)),
                    )
                )
            elif not matched_fields:
                honest_negative_signals.append(domain.domain)

        # Frailty / geriatric-vulnerability / SDOH pass. Adds Tier-1 documentation-of-existing-fact
        # items and Tier-2 seed actions ONLY. It never writes a status label or likelihood.
        frailty_gaps, frailty_negatives, seed_actions = self._frailty_pass(case_view)
        domain_gaps.extend(frailty_gaps)
        honest_negative_signals.extend(frailty_negatives)

        return GapAnalysisVerdict(
            case_id=case_id,
            judge_id=self.judge_id,
            judge_version=self.judge_version,
            kb_version=KB_VERSION,
            condition_matched=(condition.condition if condition else None),
            domain_gaps=domain_gaps,
            honest_negative_signals=honest_negative_signals,
            rationale=rationale,
            seed_actions=seed_actions,
        )

    def _frailty_pass(
        self, case_view: dict[str, Any]
    ) -> tuple[list[OutputItem], list[str], list[RecommendedAction]]:
        """Surface frailty necessity that is PRESENT but under-documented (Tier 1), and seed
        independently-indicated Tier-2 actions (which must still pass the integrity gate).

        Never asserts a status label. Absent fields -> honest-negative (never default-to-inpatient).
        SDOH signals with necessity_link_required only seed Tier-2 actions (gate-subject) unless a
        care-delivery linkage is documented — they do not become Tier-1 necessity on their own.
        """
        gaps: list[OutputItem] = []
        negatives: list[str] = []
        seeds: list[RecommendedAction] = []

        for signal in self._kb.frailty_signals:  # stable KB load order -> deterministic
            value = _read_frailty_field(case_view, signal.decision_time_field)
            if value in (None, "", "unknown"):
                negatives.append(f"frailty:{signal.signal}")
                continue

            field_label = f"current_visit.{signal.decision_time_field}"
            # SDOH boundary: a necessity-link-required signal does not become Tier-1 necessity unless
            # the record documents the care-delivery linkage. Otherwise it only seeds a gate-subject
            # Tier-2 social-work action.
            care_linkage = _has_care_delivery_linkage(case_view)
            emit_tier1 = (not signal.necessity_link_required) or care_linkage

            if emit_tier1:
                cite = signal.citations[0].ref_id if signal.citations else ""
                gaps.append(
                    OutputItem(
                        tier=1,
                        text=f"Document existing necessity (frailty: {signal.signal}): {signal.under_documentation_gap}",
                        source_tag="documentation_of_existing_fact",
                        basis=f"frailty signal '{signal.signal}' (existing fact; KB cite {cite})",
                        supporting_evidence=[f"{field_label}: {value}"],
                        strength=STRENGTH_MODERATE,
                    )
                )

            # Seed independently-indicated Tier-2 actions. helps_status=False: surfaced for care,
            # never to qualify status. They route through the integrity gate in the engine.
            for n, desc in enumerate(signal.independently_indicated_actions):
                seeds.append(
                    RecommendedAction(
                        action_id=f"frailty-{signal.signal}-{n}",
                        description=desc,
                        provenance="clinically_indicated",
                        indication_tag="independently_indicated",
                        helps_status=False,
                        is_new_care=True,
                        rationale=f"independently indicated for documented {signal.signal}",
                    )
                )

        return gaps, negatives, seeds


def _read_frailty_field(case_view: dict[str, Any], field_name: str) -> Any:
    """Read a frailty field from the decision-time view (current_visit first, then top level)."""
    current = case_view.get("current_visit", {}) or {}
    if field_name in current:
        return current[field_name]
    return case_view.get(field_name)


def _has_care_delivery_linkage(case_view: dict[str, Any]) -> bool:
    """True if the record documents that a social/functional barrier prevents safe delivery of
    otherwise-needed medical care (the SDOH medical-necessity boundary). Decision-time only."""
    current = case_view.get("current_visit", {}) or {}
    return bool(current.get("care_delivery_barrier_documented", False))


def _haystack(case_view: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in _SCANNED_FIELDS:
        parts.append(_flatten(case_view.get(key)))
    return " ".join(parts).lower()


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {_flatten(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def _matched_fields(case_view: dict[str, Any], clues: list[str]) -> list[str]:
    """Return sorted dotted field labels whose text overlaps any escalation clue token."""
    tokens = _clue_tokens(clues)
    if not tokens:
        return []
    matches: set[str] = set()
    for key in _SCANNED_FIELDS:
        value = case_view.get(key)
        if isinstance(value, dict):
            for k, v in value.items():
                if k == "documentation_gaps":
                    continue  # do not match a gap against the gap list itself (circular)
                if _overlaps(_flatten(v).lower(), tokens):
                    matches.add(f"{key}.{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                if _overlaps(_flatten(v).lower(), tokens):
                    matches.add(f"{key}[{i}]")
        elif value is not None:
            if _overlaps(str(value).lower(), tokens):
                matches.add(key)
    return sorted(matches)


def _clue_tokens(clues: list[str]) -> set[str]:
    tokens: set[str] = set()
    for clue in clues:
        for word in clue.lower().replace("/", " ").replace("(", " ").replace(")", " ").split():
            word = word.strip(".,;:")
            if len(word) >= 5:  # skip short/common words to reduce noise
                tokens.add(word)
    return tokens


def _overlaps(text: str, tokens: set[str]) -> bool:
    return any(tok in text for tok in tokens)


def _already_documented(case_view: dict[str, Any]) -> set[str]:
    current = case_view.get("current_visit", {}) or {}
    gaps = current.get("documentation_gaps", []) or []
    return {str(g).lower() for g in gaps}


def _gap_already_captured(domain: GapDomain, already: set[str]) -> bool:
    """True if the status judge already surfaced a gap covering this domain (avoid duplicates)."""
    needle = domain.domain.replace("_", " ")
    return any(needle in g for g in already)


def _strength(match_count: int) -> str:
    if match_count >= 3:
        return STRENGTH_CLEAR
    if match_count == 2:
        return STRENGTH_MODERATE
    return STRENGTH_BORDERLINE
