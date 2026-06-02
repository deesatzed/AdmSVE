"""Provenance firewall for the knowledge base.

The KB ingests only PUBLIC / PEER-REVIEWED / PUBLIC-PAYER-POLICY / DERIVED-CONCEPT facts. There is
deliberately NO ``proprietary`` provenance value: proprietary licensed-criteria content
(InterQual / MCG / Milliman) is structurally inexpressible in the KB. That is the enforcement —
not a convention. The leakage scanner is a second, syntactic backstop; this enum is the primary,
structural one.

Every KB entry MUST carry a provenance from this closed set AND at least one Citation pointing at
its public/peer-reviewed source, validated at load time (see kb.__init__.load_kb).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Provenance(str, Enum):
    """Closed set. No proprietary member by design (the structural firewall)."""

    CMS_PUBLIC = "cms_public"  # CMS regulatory layer (Two-Midnight, IPO, NOTICE Act, WISeR, AHCAH)
    PEER_REVIEWED = "peer_reviewed"  # named peer-reviewed studies / specialty guidelines
    PUBLIC_PAYER_POLICY = "public_payer_policy"  # publicly published payer/provider policy documents
    DERIVED_CONCEPT = "derived_concept"  # synthesizing scaffold (e.g., the gap-analysis domain framing)


@dataclass(frozen=True)
class Citation:
    """A pointer to a public / peer-reviewed source. No proprietary criteria content is stored."""

    ref_id: str  # short stable id, e.g. "chang_2020", "acc_aha_acs_2025", "cms_two_midnight"
    source: str  # human-readable source name (journal / guideline body / agency)
    year: int
    locator: str = ""  # section / table / rule anchor
    note: str = ""


def coerce_provenance(value: str, ctx: str) -> Provenance:
    """Map a string to a Provenance, raising on anything outside the closed set.

    An unknown value (including any attempt to encode 'proprietary' / a trademark) fails closed.
    """
    try:
        return Provenance(value)
    except ValueError as exc:
        raise ValueError(
            f"{ctx}: invalid provenance '{value}'. Allowed: {[p.value for p in Provenance]}. "
            "Proprietary licensed-criteria content is not ingestible."
        ) from exc


def parse_citations(raw: list[dict] | None, ctx: str) -> tuple[Citation, ...]:
    """Parse and REQUIRE at least one citation; fail closed otherwise."""
    items = raw or []
    if not items:
        raise ValueError(f"{ctx}: every KB entry must carry at least one citation")
    out: list[Citation] = []
    for c in items:
        ref_id = (c.get("ref_id") or "").strip()
        source = (c.get("source") or "").strip()
        if not ref_id or not source:
            raise ValueError(f"{ctx}: citation requires non-empty ref_id and source")
        out.append(
            Citation(
                ref_id=ref_id,
                source=source,
                year=int(c.get("year", 0)),
                locator=str(c.get("locator", "")),
                note=str(c.get("note", "")),
            )
        )
    return tuple(out)
