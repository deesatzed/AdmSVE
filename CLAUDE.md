# CLAUDE.md — Admission Status Qualification & Documentation-Integrity Engine (Phase 1)

Guidance for any future Claude Code session in this repo. These rules are **non-negotiable** and
inherited from `Admission_Status_Engine_Phase1_Handoff.md` and `CLAUDE_GOAL_Admission_Engine.md`.

## Supreme constraint

**Status accuracy, never status inflation.** The engine surfaces (a) documentation of medical
necessity that already exists and (b) actions that are independently clinically indicated regardless
of billing. It must NEVER recommend a test/treatment/"documentation" whose justification is
qualifying for a higher payment tier. If a case does not meet inpatient criteria, say so plainly.
Over-calling inpatient is a **tracked failure**, not a success.

## Hard rules (violating any one fails the task)

1. **Synthetic data only.** No real PHI, no real claims, no Temple data. `mode` must be `synthetic`;
   `source: real_ehr|real_claims` is rejected by the contract.
2. **No proprietary criteria text.** Never write/paste/paraphrase/cache/output InterQual or
   MCG/Milliman criteria content. The licensed conformance check is a **stubbed abstract port**
   (`judges/criteria_interface.py`). The public CMS layer (Two-Midnight, IPO concepts) is our own
   logic in `payer_routing.py`. The `scan-leakage` command + `test_criteria_leakage_scan.py` enforce
   this; keep them green.
3. **Integrity gate is mandatory.** Any "new testing/treatment" action must pass BOTH the
   status-conformance check AND the independent clinical-indication check (`integrity_gate/gate.py`),
   or be **suppressed and logged**. Planted-case suppression must stay at 100%.
4. **Recommender behind a swappable abstraction.** OpenEvidence is the intended engine but must stay
   mockable (`recommender/base.py` ABC; `recommender/mock_oe.py` stub). Never hardcode a hard OE
   dependency. No network calls; no secrets.
5. **Silent.** No live determination, no UR-facing surface, no real-time operation.
6. **Leakage discipline.** The recommender only ever sees `recommender_visible_view(payload)`. Any
   post-decision/adjudication/post-discharge field fails the run closed
   (`contracts/case_snapshot.py`).
7. **Pin versions + snapshot every adjudication** into the hash-chained trace
   (`trace.py`, reused from EMEX).
8. **Surface, do not resolve, the open decisions** (`prereg/OPEN_DECISIONS.md`). Code against the
   marked placeholders; do not silently pick.

## What NOT to do

No live/real-time/UR-facing surface; no readiness/deployment claims; no monetization/referral/
governance features; no resolving the four open decisions; no real data until the §8 compliance gate
(approved environment + BAA + IRB/QI) is documented.

## Reuse provenance

`hashing.py` and `trace.py` are reused from the sibling `ClinClaw/EMEX` project; the leakage-scan,
contract, and tiered-artifact patterns are adapted from it.

## Verify

```bash
python -m admission_engine.cli gen-fixtures --out fixtures/synthetic_cases --n 60
python -m admission_engine.cli run-corpus  --in fixtures/synthetic_cases --out artifacts/run1
python -m py_compile $(find src -name '*.py')
pytest -q
```
