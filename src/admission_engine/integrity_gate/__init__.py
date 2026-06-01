"""Integrity gate: the False-Claims-Act guardrail.

An action that would constitute NEW testing/treatment may be surfaced ONLY if it passes BOTH
the status-conformance check AND the independent clinical-indication check. Status-helpful but
not-independently-indicated actions are SUPPRESSED and LOGGED — never recommended
(handoff Invariant 2; goal hard rule #3).
"""

from .gate import GateDecision, IntegrityGate, SuppressionLogEntry

__all__ = ["GateDecision", "IntegrityGate", "SuppressionLogEntry"]
