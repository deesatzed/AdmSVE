"""Redactor abstraction (swappable port) + result types.

A Redactor takes text and returns the redacted text plus the spans it removed. Spans are
character offsets so multiple backends can be merged deterministically (union, then apply).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# Placeholder format: [CATEGORY]. The category is the entity type (e.g. NAME, MRN, SSN).
PHI_PLACEHOLDER = "[{label}]"


@dataclass(frozen=True)
class RedactionSpan:
    """A single detected PHI/PII span (half-open [start, end) char offsets)."""

    start: int
    end: int
    label: str  # entity category, e.g. "NAME", "MRN", "EMAIL"
    source: str  # which backend found it, e.g. "deterministic", "openmed"
    score: float = 1.0  # 1.0 for deterministic regex; model confidence otherwise

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end})")


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    spans: tuple[RedactionSpan, ...] = field(default_factory=tuple)

    @property
    def findings(self) -> dict[str, int]:
        """Count of redactions per label (for the redaction report)."""
        counts: dict[str, int] = {}
        for s in self.spans:
            counts[s.label] = counts.get(s.label, 0) + 1
        return counts

    @property
    def clean(self) -> bool:
        return len(self.spans) == 0


class Redactor(ABC):
    """Swappable redactor port. Implementations must be safe to call on any text.

    A redactor MUST NOT raise on ordinary input; if a backend cannot run, it must degrade to
    finding nothing rather than passing unredacted text through (the LayeredRedactor guarantees
    the deterministic floor still applies).
    """

    redactor_id: str = "abstract"
    redactor_version: str = "0"

    @abstractmethod
    def find_spans(self, text: str) -> list[RedactionSpan]:
        """Return detected PHI/PII spans. Must not raise on ordinary text."""
        raise NotImplementedError

    def redact(self, text: str) -> RedactionResult:
        spans = merge_spans(self.find_spans(text))
        return RedactionResult(redacted_text=apply_spans(text, spans), spans=tuple(spans))


def merge_spans(spans: list[RedactionSpan]) -> list[RedactionSpan]:
    """Sort and merge overlapping spans deterministically. Overlaps keep the earliest start and
    widest end; the label of the longest contributing span wins (ties -> alphabetical for
    determinism)."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (s.start, s.end, s.label, s.source))
    merged: list[RedactionSpan] = []
    for s in ordered:
        if merged and s.start < merged[-1].end:
            prev = merged[-1]
            new_end = max(prev.end, s.end)
            # choose label from the longer original span; tie-break alphabetically
            cand = max(
                (prev, s),
                key=lambda x: (x.end - x.start, x.label),
            )
            merged[-1] = RedactionSpan(
                start=prev.start,
                end=new_end,
                label=cand.label,
                source="merged" if prev.source != s.source else prev.source,
                score=min(prev.score, s.score),
            )
        else:
            merged.append(s)
    return merged


def apply_spans(text: str, spans: list[RedactionSpan]) -> str:
    """Replace each span with its [LABEL] placeholder, right-to-left to keep offsets valid."""
    out = text
    for s in sorted(spans, key=lambda x: x.start, reverse=True):
        placeholder = PHI_PLACEHOLDER.format(label=s.label)
        out = out[: s.start] + placeholder + out[s.end :]
    return out
