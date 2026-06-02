"""Optional OpenMed model backend for PHI/PII redaction.

GATED: this backend loads a neural model and an external dependency. It must only be activated
inside the approved §8 PHI environment (see prereg/REAL_DATA_READINESS.md). It is NEVER imported at
package import time — `openmed` / `transformers` are optional extras. Absent the dependency or the
gate, the engine uses the deterministic floor only (fail-safe, never fail-open on PHI).

Cross-platform: the portable path is PyTorch/transformers (CPU + CUDA), which the OpenMed model
cards confirm runs on Linux/Windows/macOS. On Apple Silicon the MLX 8-bit variant may be selected
for speed; the openmed library falls back to PyTorch off Apple automatically. We do NOT hard-require
MLX, so the same code runs on all three platforms.

The model cards are explicit that these are general-PII models ("not a clinical PHI model… use
alongside deterministic regex pre-filters"). Hence this is a recall booster on top of the floor,
not a replacement for it.
"""

from __future__ import annotations

import os

from .base import RedactionSpan, Redactor

# Default portable model. The MLX 8-bit variant is Apple-Silicon-only; the PyTorch base is portable.
DEFAULT_MODEL = "OpenMed/privacy-filter-multilingual"
APPLE_MLX_MODEL = "OpenMed/privacy-filter-nemotron-mlx-8bit"

# Environment gate. The backend refuses to load unless the approved-environment flag is set,
# so the model cannot be invoked outside the §8-cleared deployment by accident.
ENV_GATE = "ADMISSION_ENGINE_PHI_ENV_APPROVED"

# Minimum confidence to accept a model span (recalibrate on a domain eval set per the model card).
DEFAULT_MIN_SCORE = 0.5


class OpenMedRedactor(Redactor):
    """Lazy-loading OpenMed token-classification backend. Construct only inside the approved env."""

    redactor_id = "openmed"

    def __init__(
        self,
        model_name: str | None = None,
        min_score: float = DEFAULT_MIN_SCORE,
        require_env_gate: bool = True,
    ) -> None:
        if require_env_gate and os.environ.get(ENV_GATE) != "1":
            raise RuntimeError(
                f"OpenMedRedactor refused to load: environment gate {ENV_GATE}=1 not set. "
                "This model backend may only run inside the approved §8 PHI environment "
                "(see prereg/REAL_DATA_READINESS.md). Use DeterministicRedactor / LayeredRedactor "
                "for synthetic or ungated runs."
            )
        self.model_name = model_name or DEFAULT_MODEL
        self.redactor_version = f"openmed::{self.model_name}"
        self.min_score = min_score
        self._pipe = None  # lazily constructed on first use

    def _ensure_pipe(self):
        if self._pipe is not None:
            return
        try:
            # Portable path: openmed library (handles MLX-on-Apple vs PyTorch-elsewhere fallback).
            from openmed.mlx.inference import PrivacyFilterMLXPipeline  # type: ignore
            from huggingface_hub import snapshot_download  # type: ignore

            path = snapshot_download(self.model_name)
            self._pipe = ("mlx", PrivacyFilterMLXPipeline(path))
            return
        except Exception:
            pass
        # Fallback to a standard transformers token-classification pipeline (CPU/CUDA, all platforms).
        from transformers import pipeline  # type: ignore

        self._pipe = ("hf", pipeline("token-classification", model=self.model_name, aggregation_strategy="simple"))

    def find_spans(self, text: str) -> list[RedactionSpan]:
        self._ensure_pipe()
        kind, pipe = self._pipe  # type: ignore[misc]
        raw = pipe(text)
        spans: list[RedactionSpan] = []
        for ent in raw:
            score = float(ent.get("score", 0.0))
            if score < self.min_score:
                continue
            start = ent.get("start")
            end = ent.get("end")
            if start is None or end is None:
                continue
            label = str(ent.get("entity_group") or ent.get("entity") or "PII").upper()
            spans.append(
                RedactionSpan(start=int(start), end=int(end), label=label, source=self.redactor_id, score=score)
            )
        return spans


def is_available() -> bool:
    """True if an OpenMed-capable backend dependency is importable (does not load any model)."""
    try:
        import transformers  # noqa: F401  # type: ignore

        return True
    except Exception:
        try:
            import openmed  # noqa: F401  # type: ignore

            return True
        except Exception:
            return False
