"""Proprietary-criteria leakage scanner.

Scans a directory tree (source, logs, generated artifacts) for any marker that would indicate
InterQual / MCG / Milliman proprietary criteria text has leaked into the repo or outputs. This is
a guardrail, NOT a place to store the very terms being scanned for in a way that resembles content
— the markers below are bare trademark tokens used only for detection.

A file is allowed to MENTION the trademarks in a compliance/guardrail context (this scanner, the
CLAUDE.md, the docs). The scan therefore distinguishes:
  - allowed files (guardrail/docs that necessarily name the trademarks), and
  - everything else, where any trademark token is a finding.
"""

from __future__ import annotations

import re
from pathlib import Path

# Bare trademark tokens (detection only — no criteria CONTENT is stored anywhere).
CRITERIA_MARKERS = ["interqual", "mcg", "milliman"]

# Match each marker as a WHOLE WORD (word boundaries), case-insensitive. This avoids false positives
# from benign substrings — e.g. the surname "McGarry" contains "mcg" but is not the MCG trademark —
# while still catching the standalone trademark and forms like "MCG/Milliman" or "MCG criteria".
_MARKER_RE = re.compile(r"\b(" + "|".join(re.escape(m) for m in CRITERIA_MARKERS) + r")\b", re.I)

# Files/dirs permitted to name the trademarks because their job is to forbid/Scan/document them.
ALLOWED_BASENAMES = {
    "leakage_scan.py",
    "criteria_interface.py",
    "CLAUDE.md",
    "README.md",
    "PRE_REGISTRATION.md",
    "OPEN_DECISIONS.md",
    "REAL_DATA_READINESS.md",
    "test_criteria_leakage_scan.py",
    "test_kb_provenance.py",
    "payer_routing.py",
    # KB firewall files: their docstrings necessarily name the trademarks to declare that the
    # proprietary InterQual-ISD/MCG element lists were deliberately NOT ingested.
    "provenance.py",
}

SCAN_SUFFIXES = {".py", ".json", ".md", ".txt", ".html", ".log"}
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", ".venv", "venv", ".benchmarks"}


def scan_path(root: Path) -> list[dict[str, str]]:
    """Return a list of findings: files (outside the allow-list) containing criteria trademark tokens."""
    findings: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if path.name in ALLOWED_BASENAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in _MARKER_RE.finditer(text):
            findings.append({"path": str(path), "marker": match.group(1).lower()})
    return findings
