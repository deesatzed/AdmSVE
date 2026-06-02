"""Optional MCP-backed redaction backend.

Calls an EXTERNAL redaction MCP server (e.g. RedaktR) over the Model Context Protocol and maps its
detected PHI spans into our RedactionSpan model. This keeps the heavy, infrastructure-bound,
non-deterministic detection pipeline (spaCy NER / Docker / Postgres / optionally MLX) OUT of our
process — it runs as a separate gated service in the approved §8 environment — while our engine
stays std-lib, portable (macOS/Linux/Windows), and deterministic at the floor.

Why this seam (evidence): RedaktR's own measured benchmark (workflow_comparison_results.json) shows
its recall advantage comes from spaCy NER (~29 items/0.93s), while the Apple-Silicon-only MLX-LLM
adds ~0.7 items for ~8.3s. So the value to tap is the NER scan, not the LLM. Prefer the server's
scan tool with technique selection that favors regex+spaCy over MLX where the server supports it.

GATING (same discipline as the OpenMed backend):
- Refuses to construct unless ADMISSION_ENGINE_PHI_ENV_APPROVED=1 (the §8 gate).
- The MCP client transport is INJECTED (no hard `mcp` dependency at import time). A real deployment
  passes a client that speaks to the RedaktR MCP server; tests pass a fake.
- FAIL-SAFE: any client error -> find_spans returns [] so the LayeredRedactor's deterministic floor
  still redacts. Redaction never fails open on PHI because the MCP server is unreachable.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from .base import RedactionSpan, Redactor

ENV_GATE = "ADMISSION_ENGINE_PHI_ENV_APPROVED"

# Tool names RedaktR exposes (README: scan_healthcare_text / redact_healthcare_text). We use the
# SCAN tool so WE apply the redaction deterministically from spans, keeping placeholder formatting
# and span-merging under our control.
DEFAULT_SCAN_TOOL = "scan_healthcare_text"

DEFAULT_MIN_SCORE = 0.5


class McpScanClient(Protocol):
    """Minimal injected client. A real one wraps an MCP session; a fake is used in tests.

    call_tool(name, arguments) must return a list of detected entities, each a dict with at least
    character offsets and a label. Supported key spellings (mapped flexibly):
      start|begin, end|stop, label|entity_group|type, score|confidence, text|word.
    """

    def call_tool(self, name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        ...


class McpRedactor(Redactor):
    redactor_id = "mcp"

    def __init__(
        self,
        client: McpScanClient,
        scan_tool: str = DEFAULT_SCAN_TOOL,
        min_score: float = DEFAULT_MIN_SCORE,
        techniques: list[str] | None = None,
        require_env_gate: bool = True,
    ) -> None:
        if require_env_gate and os.environ.get(ENV_GATE) != "1":
            raise RuntimeError(
                f"McpRedactor refused to load: environment gate {ENV_GATE}=1 not set. The external "
                "redaction MCP server may only be called inside the approved §8 PHI environment "
                "(see prereg/REAL_DATA_READINESS.md)."
            )
        self._client = client
        self._scan_tool = scan_tool
        self.min_score = min_score
        # Favor regex+spaCy over MLX per the measured yield/latency tradeoff; the server may ignore.
        self._techniques = techniques or ["regex", "spacy"]
        self.redactor_version = f"mcp::{scan_tool}"

    def find_spans(self, text: str) -> list[RedactionSpan]:
        try:
            entities = self._client.call_tool(
                self._scan_tool, {"text": text, "techniques": self._techniques}
            )
        except Exception:
            return []  # FAIL-SAFE: floor still redacts via LayeredRedactor
        return [s for s in (_to_span(e) for e in entities or []) if s is not None and s.score >= self.min_score]


def _to_span(ent: dict[str, Any]) -> RedactionSpan | None:
    """Map a flexible MCP entity dict to a RedactionSpan; return None if offsets are missing."""
    start = ent.get("start", ent.get("begin"))
    end = ent.get("end", ent.get("stop"))
    if start is None or end is None:
        return None
    label = str(ent.get("label") or ent.get("entity_group") or ent.get("type") or "PHI").upper()
    score = float(ent.get("score", ent.get("confidence", 1.0)))
    try:
        return RedactionSpan(start=int(start), end=int(end), label=label, source="mcp", score=score)
    except ValueError:
        return None
