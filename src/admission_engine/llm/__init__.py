"""Swappable LLM port.

The LLM powers the fuzzy edges (intake extraction, OE-prose parsing) and — per the user's explicit
choice — the scoring backend. It is a SWAPPABLE port (like the recommender / redaction ports):
- LLMClient: the ABC.
- StubLLMClient: deterministic, no network, no key — the default for tests + offline runs.
- EnvLLMClient: provider/model/key read from .env at runtime (NOTHING hardcoded). Cloud providers
  are gated: raw PHI may only be sent inside the approved §8 environment; otherwise the client is for
  synthetic / already-redacted text only.

Model selection is the user's: the app reads ADMISSION_ENGINE_LLM_PROVIDER + the provider's *_MODEL
from .env. Change the model any time without a code edit.
"""

from .base import LLMClient, LLMResult
from .stub_client import StubLLMClient

__all__ = ["LLMClient", "LLMResult", "StubLLMClient", "get_client"]


def get_client(force_stub: bool = False) -> LLMClient:
    """Return the configured LLM client. Defaults to the stub unless .env selects a real provider."""
    if force_stub:
        return StubLLMClient()
    from .env_client import build_from_env

    return build_from_env()
