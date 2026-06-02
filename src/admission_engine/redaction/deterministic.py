"""Deterministic regex redactor — the always-on PHI/PII floor.

Std-lib only, fully deterministic, cross-platform (macOS / Linux / Windows). Covers HIPAA Safe
Harbor-style direct identifiers that have reliable surface patterns. It is the FLOOR, not the
ceiling: free-text names embedded in narrative and other context-dependent identifiers are the
job of the optional model backend (and, ultimately, the approved environment + human review).

Pattern set is intentionally conservative and explicit so a reviewer can audit exactly what is and
is not caught. Each pattern emits a labelled span; offsets are computed so spans can be merged with
model spans deterministically.
"""

from __future__ import annotations

import re

from .base import RedactionSpan, Redactor

# (label, compiled pattern). Order is irrelevant — spans are merged by offset downstream.
# Labels are entity CATEGORIES (HIPAA-18-aligned where applicable).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("MRN", re.compile(r"\b(?:MRN|Medical Record(?: Number)?)\s*[:#]?\s*[A-Z0-9-]{4,}\b", re.I)),
    ("HEALTH_PLAN_ID", re.compile(r"\b(?:member|beneficiary|policy|subscriber)\s*(?:id|#|number)\s*[:#]?\s*[A-Z0-9-]{5,}\b", re.I)),
    ("DOB", re.compile(r"\b(?:DOB|Date of Birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I)),
    ("DATE", re.compile(r"\b(?:19|20)\d{2}[/-]\d{1,2}[/-]\d{1,2}\b")),
    ("DATE", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-](?:19|20)?\d{2}\b")),
    ("ZIP", re.compile(r"\b\d{5}(?:-\d{4})?\b(?=\s*$|\s*[,.;])")),  # conservative: zip at clause end
    # Street address: number + 1-4 capitalized words + a street suffix (no arbitrary filler words,
    # so it cannot bleed across an SSN/phone into unrelated text).
    ("ADDRESS", re.compile(r"\b\d{1,5}\s+(?:[A-Z][A-Za-z]+\.?\s+){1,4}(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Way)\b", re.I)),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("URL", re.compile(r"\bhttps?://[^\s]+\b", re.I)),
    ("ACCOUNT", re.compile(r"\b(?:account|acct)\s*(?:#|number|no)?\s*[:#]?\s*\d{6,}\b", re.I)),
    # Synthetic-fixture given-name list (deterministic; real names are the model/HITL layer's job).
    ("NAME", re.compile(r"\b(?:Jane|John|Wayne|Mary|Robert|Patricia|Michael|William|Sarah|James|Linda|David)\s+[A-Z][a-z]+\b")),
]


class DeterministicRedactor(Redactor):
    redactor_id = "deterministic_regex"
    redactor_version = "v0.1"

    def find_spans(self, text: str) -> list[RedactionSpan]:
        spans: list[RedactionSpan] = []
        for label, pattern in _PATTERNS:
            for m in pattern.finditer(text):
                spans.append(
                    RedactionSpan(
                        start=m.start(),
                        end=m.end(),
                        label=label,
                        source=self.redactor_id,
                        score=1.0,
                    )
                )
        return spans


def contains_residual_pii(text: str) -> bool:
    """True if any deterministic pattern still matches (post-redaction sanity check)."""
    return any(p.search(text) for _, p in _PATTERNS)
