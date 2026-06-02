"""Redaction tests: deterministic floor, determinism, span union, fail-safe, no-deps, env gate."""

import pytest

from admission_engine.redaction import (
    DeterministicRedactor,
    LayeredRedactor,
    RedactionResult,
)
from admission_engine.redaction.base import Redactor, RedactionSpan, merge_spans
from admission_engine.redaction.deterministic import contains_residual_pii

SAMPLE = (
    "Patient John Smith DOB: 03/15/1985 MRN: 4872910 phone 415-555-0123 "
    "email j.smith@example.com SSN 123-45-6789 lives at 123 Main Street."
)


def test_deterministic_redacts_core_identifiers():
    r = DeterministicRedactor().redact(SAMPLE)
    for token in ("123-45-6789", "j.smith@example.com", "415-555-0123", "4872910"):
        assert token not in r.redacted_text, f"{token} leaked"
    assert "[SSN]" in r.redacted_text
    assert "[EMAIL]" in r.redacted_text
    assert "[PHONE]" in r.redacted_text


def test_deterministic_is_deterministic():
    a = DeterministicRedactor().redact(SAMPLE).redacted_text
    b = DeterministicRedactor().redact(SAMPLE).redacted_text
    assert a == b


def test_findings_counts():
    r = DeterministicRedactor().redact(SAMPLE)
    assert r.findings.get("SSN") == 1
    assert r.findings.get("EMAIL") == 1
    assert not r.clean


def test_residual_pii_check_clean_after_redaction():
    redacted = DeterministicRedactor().redact(SAMPLE).redacted_text
    # The deterministic patterns should not re-match their own placeholders.
    assert not contains_residual_pii(redacted)


def test_clean_text_yields_no_spans():
    r = DeterministicRedactor().redact("The patient is stable on room air with improving vitals.")
    assert r.clean
    assert r.redacted_text == "The patient is stable on room air with improving vitals."


# --- layered + fail-safe ----------------------------------------------------


class _BrokenBackend(Redactor):
    redactor_id = "broken"

    def find_spans(self, text):
        raise RuntimeError("model unavailable")


class _ExtraBackend(Redactor):
    redactor_id = "extra"

    def find_spans(self, text):
        idx = text.find("Patient")
        if idx < 0:
            return []
        return [RedactionSpan(start=idx, end=idx + 7, label="CONTEXT", source="extra", score=0.9)]


def test_layered_floor_always_applies():
    r = LayeredRedactor().redact(SAMPLE)
    assert "123-45-6789" not in r.redacted_text


def test_failsafe_broken_backend_does_not_leak():
    """A broken optional backend must NOT drop the deterministic floor's redactions."""
    r = LayeredRedactor(extra_backends=[_BrokenBackend()]).redact(SAMPLE)
    assert "123-45-6789" not in r.redacted_text
    assert "j.smith@example.com" not in r.redacted_text
    assert "[SSN]" in r.redacted_text


def test_extra_backend_spans_are_unioned():
    r = LayeredRedactor(extra_backends=[_ExtraBackend()]).redact(SAMPLE)
    assert "[CONTEXT]" in r.redacted_text or "[NAME]" in r.redacted_text  # extra span applied


def test_layered_is_deterministic():
    outs = {LayeredRedactor().redact(SAMPLE).redacted_text for _ in range(5)}
    assert len(outs) == 1


def test_overlapping_spans_merge():
    spans = [
        RedactionSpan(0, 10, "NAME", "a"),
        RedactionSpan(5, 15, "EMAIL", "b"),  # overlaps -> merged
        RedactionSpan(20, 25, "SSN", "c"),
    ]
    merged = merge_spans(spans)
    assert len(merged) == 2
    assert merged[0].start == 0 and merged[0].end == 15


# --- no hard dependency + env gate -----------------------------------------


def test_redaction_package_has_no_hard_model_dependency():
    """Importing the redaction package must not require transformers/openmed."""
    import importlib

    mod = importlib.import_module("admission_engine.redaction")
    assert hasattr(mod, "DeterministicRedactor")
    assert hasattr(mod, "LayeredRedactor")


def test_openmed_backend_refuses_without_env_gate(monkeypatch):
    """The model backend must refuse to load outside the approved §8 environment."""
    from admission_engine.redaction.openmed_backend import ENV_GATE, OpenMedRedactor

    monkeypatch.delenv(ENV_GATE, raising=False)
    with pytest.raises(RuntimeError):
        OpenMedRedactor()  # env gate not set -> refuse


# --- MCP backend (RedaktR seam) --------------------------------------------


class _FakeMcpClient:
    """Returns a span for the substring 'John Smith' (simulates a NER scan tool)."""

    def call_tool(self, name, arguments):
        text = arguments["text"]
        i = text.find("John Smith")
        if i < 0:
            return []
        return [{"start": i, "end": i + len("John Smith"), "entity_group": "name", "score": 0.95}]


class _BrokenMcpClient:
    def call_tool(self, name, arguments):
        raise RuntimeError("MCP server unreachable")


def test_mcp_backend_refuses_without_env_gate(monkeypatch):
    from admission_engine.redaction.mcp_backend import ENV_GATE, McpRedactor

    monkeypatch.delenv(ENV_GATE, raising=False)
    with pytest.raises(RuntimeError):
        McpRedactor(_FakeMcpClient())


def test_mcp_backend_maps_spans_and_unions_with_floor(monkeypatch):
    from admission_engine.redaction.mcp_backend import ENV_GATE, McpRedactor

    monkeypatch.setenv(ENV_GATE, "1")
    red = LayeredRedactor(extra_backends=[McpRedactor(_FakeMcpClient())])
    out = red.redact(SAMPLE)
    assert "[NAME]" in out.redacted_text  # MCP-detected name
    assert "[SSN]" in out.redacted_text  # floor still applies


def test_mcp_backend_failsafe_when_server_down(monkeypatch):
    """If the MCP server errors, the deterministic floor must still redact (never fail open)."""
    from admission_engine.redaction.mcp_backend import ENV_GATE, McpRedactor

    monkeypatch.setenv(ENV_GATE, "1")
    red = LayeredRedactor(extra_backends=[McpRedactor(_BrokenMcpClient())])
    out = red.redact(SAMPLE)
    assert "123-45-6789" not in out.redacted_text
    assert "[SSN]" in out.redacted_text


def test_mcp_backend_drops_low_score(monkeypatch):
    from admission_engine.redaction.mcp_backend import ENV_GATE, McpRedactor

    monkeypatch.setenv(ENV_GATE, "1")

    class _LowScore:
        def call_tool(self, name, arguments):
            return [{"start": 0, "end": 5, "label": "name", "score": 0.1}]

    spans = McpRedactor(_LowScore(), min_score=0.5).find_spans("Hello world")
    assert spans == []
