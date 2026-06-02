"""PHI/PII redaction — a swappable, cross-platform, defense-in-depth layer.

Redaction is NOT the primary PHI control (the approved §8 environment + BAA is — see
prereg/REAL_DATA_READINESS.md). This layer is defense-in-depth on any text the engine handles.

Design (per the OpenMed model cards' own guidance: "not a substitute for compliance — use alongside
deterministic regex pre-filters"):
- DeterministicRedactor: HIPAA-18-style regex floor. Std-lib only, fully deterministic, runs on
  macOS/Linux/Windows, hash-pinnable. ALWAYS ON.
- OpenMedRedactor (optional, gated): a model backend that ADDS recall. Behind an optional extra;
  absent or failing -> the deterministic floor still redacts (fail-safe, never fail-open on PHI).
- LayeredRedactor: deterministic floor unioned with any optional backends.

Backends are swappable behind the Redactor ABC, exactly like the OE recommender and the licensed-
criteria interface.
"""

from .base import PHI_PLACEHOLDER, RedactionResult, RedactionSpan, Redactor
from .deterministic import DeterministicRedactor
from .layered import LayeredRedactor

__all__ = [
    "PHI_PLACEHOLDER",
    "RedactionResult",
    "RedactionSpan",
    "Redactor",
    "DeterministicRedactor",
    "LayeredRedactor",
]
