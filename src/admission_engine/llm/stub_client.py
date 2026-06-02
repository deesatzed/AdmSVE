"""Deterministic stub LLM client — the default for tests and offline runs.

No network, no key. Produces a stable, parseable response derived from the prompt so the intake
extractor, prose parser, and LLM recommender can be exercised end-to-end without a real model. The
stub returns a clearly-labelled deterministic stand-in; it is NEVER a substitute for a real model in
production and the app marks stub-backed output as such.
"""

from __future__ import annotations

from .base import LLMClient, LLMResult


class StubLLMClient(LLMClient):
    provider = "stub"
    model = "deterministic-stub"

    def complete(self, prompt: str, system: str = "") -> LLMResult:
        # Echo a deterministic marker plus a short digest of the prompt so callers that look for
        # structure get something stable. Real structure is produced by the caller's own
        # deterministic fallback when provider==stub (see intake/oe_prose modules).
        text = "[STUB-LLM] deterministic response; no model configured. " + _digest(prompt)
        return self._result(text, prompt, system)


def _digest(prompt: str) -> str:
    words = [w for w in prompt.split() if w.isalpha()]
    return " ".join(words[:12])
