"""Admission Status Qualification & Documentation-Integrity Engine — Phase 1.

Silent, retrospective, synthetic-only validation harness. See CLAUDE.md and README.md.

NON-NEGOTIABLE INVARIANTS (Phase 1):
- Status accuracy, never status inflation.
- Synthetic data only; no real PHI/claims.
- No proprietary licensed-criteria text anywhere (see leakage_scan.py for the enforced ban).
- Integrity gate: a "new testing/treatment" action is surfaced only if it passes BOTH the
  status-conformance check AND an independent clinical-indication check; otherwise suppressed + logged.
- Silent: no live determination, no UR-facing surface, no real-time.
"""

__version__ = "0.1.0"

# Version pins surfaced in every adjudication snapshot (handoff Invariant 6).
# These are deliberately Phase-1 placeholders; real effective-dates/criteria versions are
# pinned via the pre-registration document before any real run (see prereg/).
ENGINE_VERSION = "admission_engine.v0.1-synthetic"
CMS_RULE_EFFECTIVE_DATE = "PLACEHOLDER_CY2026_OPPS"  # pin real effective-date in prereg/
CRITERIA_INTERFACE_VERSION = "stubbed-no-proprietary-text.v0.1"
