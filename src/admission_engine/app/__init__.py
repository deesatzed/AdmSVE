"""Localhost clinician app surface (FastAPI). Steps 2-7 of the workflow.

Localhost-only, no auth (login deferred). Calls the REAL Python engine + redaction + LLM directly
(no logic re-implemented client-side). The LLM recommender is the DEFAULT scoring backend; the
deterministic Mock remains the test/audit backstop. Redaction runs BEFORE any LLM call.
"""
