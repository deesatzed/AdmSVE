"""Intake: turn pasted decision-time clinical text into a validated case-snapshot.

Step 2 of the clinician workflow. Redaction runs BEFORE the LLM (the extractor receives already-
redacted text). No clinician confirmation step (the user's choice): the extractor produces a
contract-valid snapshot and the engine runs; the output is an adjunct that updates as more info is
added. The leakage firewall (contracts/case_snapshot.py) still applies — post-decision content is
rejected.
"""

from .extractor import IntakeResult, extract_case_snapshot

__all__ = ["IntakeResult", "extract_case_snapshot"]
