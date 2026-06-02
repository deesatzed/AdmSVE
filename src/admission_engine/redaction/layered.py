"""Layered redactor: deterministic floor + optional model backends.

The deterministic regex floor ALWAYS runs. Optional backends (e.g. the OpenMed model) only ADD
spans. If an optional backend raises or is unavailable, the floor still applies — redaction never
fails open on PHI. Spans from all backends are merged by offset (union), then applied once.
"""

from __future__ import annotations

from .base import RedactionResult, RedactionSpan, Redactor, apply_spans, merge_spans
from .deterministic import DeterministicRedactor


class LayeredRedactor(Redactor):
    redactor_id = "layered"
    redactor_version = "v0.1"

    def __init__(self, extra_backends: list[Redactor] | None = None) -> None:
        # The deterministic floor is always present and always first.
        self._floor = DeterministicRedactor()
        self._extra = list(extra_backends or [])

    @property
    def backends(self) -> list[str]:
        return [self._floor.redactor_id, *(b.redactor_id for b in self._extra)]

    def find_spans(self, text: str) -> list[RedactionSpan]:
        spans: list[RedactionSpan] = list(self._floor.find_spans(text))
        for backend in self._extra:
            try:
                spans.extend(backend.find_spans(text))
            except Exception:
                # Fail SAFE: an optional backend failure must not drop the floor's redactions
                # nor leak text. We simply proceed with what we have (at minimum, the floor).
                continue
        return spans

    def redact(self, text: str) -> RedactionResult:
        spans = merge_spans(self.find_spans(text))
        return RedactionResult(redacted_text=apply_spans(text, spans), spans=tuple(spans))
