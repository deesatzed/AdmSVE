"""Env-driven LLM client: provider/model/key from .env. Nothing hardcoded.

Supported providers (selected by ADMISSION_ENGINE_LLM_PROVIDER):
- "stub"       -> StubLLMClient (deterministic, no network, default).
- "openrouter" -> OpenRouter chat-completions (OPENROUTER_API_KEY, OPENROUTER_MODEL).
- "anthropic"  -> Anthropic messages API (ANTHROPIC_API_KEY, ANTHROPIC_MODEL).

PHI GATE: openrouter/anthropic are CLOUD APIs. They may only receive raw PHI inside the approved §8
environment (ADMISSION_ENGINE_PHI_ENV_APPROVED=1). The app always redacts BEFORE calling the LLM, so
in normal use only synthetic / redacted text is sent — but the gate is a hard backstop callers can
consult via `is_cloud` before sending unredacted text.

httpx is an OPTIONAL dependency (the `llm` extra). If a cloud provider is selected but httpx is
absent, construction raises a clear error; the app falls back to the stub.
"""

from __future__ import annotations

import json
import os

from .base import LLMClient, LLMResult, load_dotenv_once
from .stub_client import StubLLMClient

PHI_ENV_GATE = "ADMISSION_ENGINE_PHI_ENV_APPROVED"


def build_from_env() -> LLMClient:
    load_dotenv_once()
    provider = os.environ.get("ADMISSION_ENGINE_LLM_PROVIDER", "stub").strip().lower()
    if provider in ("", "stub"):
        return StubLLMClient()
    if provider == "openrouter":
        return _HttpLLMClient(
            provider="openrouter",
            model=os.environ.get("OPENROUTER_MODEL", "").strip(),
            api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
            url="https://openrouter.ai/api/v1/chat/completions",
            style="openai",
        )
    if provider == "anthropic":
        return _HttpLLMClient(
            provider="anthropic",
            model=os.environ.get("ANTHROPIC_MODEL", "").strip(),
            api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            url="https://api.anthropic.com/v1/messages",
            style="anthropic",
        )
    raise ValueError(f"Unknown ADMISSION_ENGINE_LLM_PROVIDER '{provider}' (use stub|openrouter|anthropic)")


class _HttpLLMClient(LLMClient):
    is_cloud = True

    def __init__(self, provider: str, model: str, api_key: str, url: str, style: str) -> None:
        if not model:
            raise ValueError(f"{provider}: model id not set in .env (set the *_MODEL variable)")
        if not api_key:
            raise ValueError(f"{provider}: API key not set in .env")
        self.provider = provider
        self.model = model
        self._api_key = api_key
        self._url = url
        self._style = style
        self._timeout = float(os.environ.get("ADMISSION_ENGINE_LLM_TIMEOUT_SECONDS", "60"))
        self._max_tokens = int(os.environ.get("ADMISSION_ENGINE_LLM_MAX_TOKENS", "2000"))

    def assert_phi_allowed(self) -> None:
        """Caller invokes this before sending UNREDACTED text. Cloud requires the §8 gate."""
        if os.environ.get(PHI_ENV_GATE) != "1":
            raise RuntimeError(
                f"{self.provider} is a cloud API; sending raw PHI requires {PHI_ENV_GATE}=1 (the "
                "approved §8 environment). The app redacts before calling the LLM; only "
                "synthetic/redacted text may be sent otherwise."
            )

    def complete(self, prompt: str, system: str = "") -> LLMResult:
        try:
            import httpx  # optional dep (llm extra)
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "httpx not installed; `pip install -e \".[llm]\"` to use a cloud LLM provider"
            ) from exc

        if self._style == "anthropic":
            headers = {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": self.model,
                "max_tokens": self._max_tokens,
                "system": system or "",
                "messages": [{"role": "user", "content": prompt}],
            }
        else:  # openai-style (openrouter)
            headers = {"Authorization": f"Bearer {self._api_key}", "content-type": "application/json"}
            messages = ([{"role": "system", "content": system}] if system else []) + [
                {"role": "user", "content": prompt}
            ]
            payload = {"model": self.model, "max_tokens": self._max_tokens, "messages": messages}

        resp = httpx.post(self._url, headers=headers, json=payload, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        text = _extract_text(self._style, data)
        return self._result(text, prompt, system)


def _extract_text(style: str, data: dict) -> str:
    if style == "anthropic":
        parts = data.get("content", [])
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    # openai-style
    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return json.dumps(data)[:0]  # empty on unexpected shape
