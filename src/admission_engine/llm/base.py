"""LLM port: the ABC + result type, and a std-lib .env loader (no python-dotenv dependency)."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..hashing import hash_text


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str  # the exact model id used (for the audit trace)
    provider: str
    prompt_hash: str  # hash of (system + prompt) for auditability

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class LLMClient(ABC):
    provider: str = "abstract"
    model: str = "none"

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> LLMResult:
        """Return a completion. Implementations must not raise on ordinary input; on transport
        failure they should raise a clear error the caller can fail-closed on."""
        raise NotImplementedError

    def _result(self, text: str, prompt: str, system: str) -> LLMResult:
        return LLMResult(
            text=text,
            model=self.model,
            provider=self.provider,
            prompt_hash=hash_text(system + "\n\n" + prompt),
        )


# --- std-lib .env loader ----------------------------------------------------

_ENV_LOADED = False


def load_dotenv_once(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into os.environ if not already present. Std-lib only.

    Does not override variables already set in the real environment (those win), so a deployment
    can use real env vars instead of a file. Never logs values.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    env_path = path or _find_env()
    if env_path is None or not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _find_env() -> Path | None:
    """Search upward from the package for a .env (repo root)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
        if (parent / "pyproject.toml").is_file():
            return parent / ".env"  # repo root; may not exist yet
    return None
