"""Citation-tagged knowledge base for the admission-status engine.

Ingests ONLY public / peer-reviewed / public-payer-policy / derived-concept facts (see
provenance.py). Pure std-lib: data lives in JSON under kb/data/ and loads into frozen dataclasses.
Deterministic: files and condition slugs are read in sorted order so the KB (and any trace that
pins KB_VERSION) is byte-reproducible.

NO proprietary licensed-criteria text appears anywhere in this package or its data — the
proprietary criteria element lists from the source literature (§2.2) were deliberately NOT
ingested (see provenance.py for the firewall). The leakage scanner covers this directory as a
backstop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .provenance import Citation, Provenance, coerce_provenance, parse_citations

KB_VERSION = "admission_engine.kb.v0.2"
KB_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class RegulatoryItem:
    key: str
    summary: str
    effective: str
    provenance: Provenance
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class GapDomain:
    domain: str
    observation_leaning: tuple[str, ...]
    inpatient_escalation_clues: tuple[str, ...]
    typical_documentation_gap: str
    provenance: Provenance
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class OverrideFactor:
    factor: str
    direction: str  # "increases_admission" | "decreases_admission" | "influences_triage"
    odds_ratio: float
    provenance: Provenance
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class FrailtySignal:
    """A frailty / geriatric-vulnerability / SDOH signal.

    A signal NEVER adds status weight. It can only (a) trigger a Tier-1 prompt to document a frailty
    fact already present in the record, or (b) seed an independently-indicated Tier-2 action that
    must pass the integrity gate. ``necessity_link_required`` marks signals (e.g. social support)
    that establish medical necessity ONLY when tied to a care-delivery failure (the SDOH boundary).
    """

    signal: str
    decision_time_field: str  # which decision-time case field carries the fact
    under_documentation_gap: str  # Tier-1 documentation text
    predicts: str  # DESCRIPTIVE interpretation (no fabricated effect sizes)
    necessity_link_required: bool
    independently_indicated_actions: tuple[str, ...]  # Tier-2 seeds (must pass the gate)
    provenance: Provenance
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class ConditionEntry:
    condition: str  # slug, e.g. "syncope"
    aliases: tuple[str, ...]  # presenting-problem synonyms for lookup
    si_thresholds: tuple[str, ...]
    is_requirements: tuple[str, ...]
    two_midnight_expectation: str
    denial_downgrade_triggers: tuple[str, ...]
    overturn_support_factors: tuple[str, ...]
    provenance: Provenance
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class KnowledgeBase:
    version: str
    regulatory_state: tuple[RegulatoryItem, ...]
    gap_domains: tuple[GapDomain, ...]
    override_factors: tuple[OverrideFactor, ...]
    frailty_signals: tuple[FrailtySignal, ...]
    conditions: tuple[ConditionEntry, ...]

    def condition_for(self, presenting_problem: str) -> ConditionEntry | None:
        """Resolve a condition by presenting problem (slug or alias), deterministically.

        Returns None when no condition matches — the engine must still run (no fabrication).
        """
        text = (presenting_problem or "").strip().lower()
        if not text:
            return None
        for cond in self.conditions:  # already in sorted/stable order
            if cond.condition in text:
                return cond
            for alias in cond.aliases:
                if alias and alias.lower() in text:
                    return cond
        return None


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _str_tuple(value) -> tuple[str, ...]:
    return tuple(str(v) for v in (value or []))


def _build_regulatory(raw: list[dict]) -> tuple[RegulatoryItem, ...]:
    out: list[RegulatoryItem] = []
    for i, e in enumerate(raw):
        ctx = f"regulatory_state[{i}]"
        out.append(
            RegulatoryItem(
                key=e["key"],
                summary=e["summary"],
                effective=str(e.get("effective", "")),
                provenance=coerce_provenance(e["provenance"], ctx),
                citations=parse_citations(e.get("citations"), ctx),
            )
        )
    return tuple(out)


def _build_domains(raw: list[dict]) -> tuple[GapDomain, ...]:
    out: list[GapDomain] = []
    for i, e in enumerate(raw):
        ctx = f"gap_domains[{i}]"
        out.append(
            GapDomain(
                domain=e["domain"],
                observation_leaning=_str_tuple(e.get("observation_leaning")),
                inpatient_escalation_clues=_str_tuple(e.get("inpatient_escalation_clues")),
                typical_documentation_gap=e["typical_documentation_gap"],
                provenance=coerce_provenance(e["provenance"], ctx),
                citations=parse_citations(e.get("citations"), ctx),
            )
        )
    return tuple(out)


def _build_overrides(raw: list[dict]) -> tuple[OverrideFactor, ...]:
    out: list[OverrideFactor] = []
    for i, e in enumerate(raw):
        ctx = f"override_factors[{i}]"
        out.append(
            OverrideFactor(
                factor=e["factor"],
                direction=e.get("direction", "influences_triage"),
                odds_ratio=float(e.get("odds_ratio", 0.0)),
                provenance=coerce_provenance(e["provenance"], ctx),
                citations=parse_citations(e.get("citations"), ctx),
            )
        )
    return tuple(out)


def _build_frailty(raw: list[dict]) -> tuple[FrailtySignal, ...]:
    out: list[FrailtySignal] = []
    for i, e in enumerate(raw):
        ctx = f"frailty_signals[{i}]"
        out.append(
            FrailtySignal(
                signal=e["signal"],
                decision_time_field=e["decision_time_field"],
                under_documentation_gap=e["under_documentation_gap"],
                predicts=str(e.get("predicts", "")),
                necessity_link_required=bool(e.get("necessity_link_required", False)),
                independently_indicated_actions=_str_tuple(e.get("independently_indicated_actions")),
                provenance=coerce_provenance(e["provenance"], ctx),
                citations=parse_citations(e.get("citations"), ctx),
            )
        )
    return tuple(out)


def _build_condition(raw: dict, ctx: str) -> ConditionEntry:
    return ConditionEntry(
        condition=raw["condition"],
        aliases=_str_tuple(raw.get("aliases")),
        si_thresholds=_str_tuple(raw.get("si_thresholds")),
        is_requirements=_str_tuple(raw.get("is_requirements")),
        two_midnight_expectation=str(raw.get("two_midnight_expectation", "")),
        denial_downgrade_triggers=_str_tuple(raw.get("denial_downgrade_triggers")),
        overturn_support_factors=_str_tuple(raw.get("overturn_support_factors")),
        provenance=coerce_provenance(raw["provenance"], ctx),
        citations=parse_citations(raw.get("citations"), ctx),
    )


@lru_cache(maxsize=1)
def load_kb() -> KnowledgeBase:
    """Load and validate the KB deterministically. Cached as a frozen singleton."""
    regulatory = _build_regulatory(_load_json(KB_DATA_DIR / "regulatory_state.json"))
    domains = _build_domains(_load_json(KB_DATA_DIR / "gap_domains.json"))
    overrides = _build_overrides(_load_json(KB_DATA_DIR / "override_factors.json"))
    frailty = _build_frailty(_load_json(KB_DATA_DIR / "frailty_signals.json"))

    conditions: list[ConditionEntry] = []
    for path in sorted((KB_DATA_DIR / "conditions").glob("*.json")):
        conditions.append(_build_condition(_load_json(path), ctx=f"conditions/{path.name}"))

    return KnowledgeBase(
        version=KB_VERSION,
        regulatory_state=regulatory,
        gap_domains=domains,
        override_factors=overrides,
        frailty_signals=frailty,
        conditions=tuple(conditions),
    )


def all_entries(kb: KnowledgeBase) -> list:
    """Flat list of every provenance-bearing entry (for the provenance lint/tests)."""
    return [
        *kb.regulatory_state,
        *kb.gap_domains,
        *kb.override_factors,
        *kb.frailty_signals,
        *kb.conditions,
    ]
