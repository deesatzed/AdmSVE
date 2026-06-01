# Admission Status Qualification & Documentation-Integrity Engine — Phase 1

A **silent, retrospective, synthetic-only** validation harness that predicts whether a case meets
**inpatient** vs **observation/outpatient** criteria and surfaces the documentation and
independently-indicated actions that would *accurately* reflect medical necessity — scored against a
final adjudicated status. **Status accuracy, never status inflation.**

This is a Phase-1 greenfield build. It touches **no real PHI/claims**, embeds **no proprietary
InterQual/MCG criteria text**, and affects **no live case**. Everything runs on **synthetic
fixtures**.

## What it does (pipeline)

```
case snapshot  ──validate + assert-no-leakage──▶  recommender-visible view
      │                                                   │
      │                                          recommender (swappable; mock OE stub)
      │                                                   │
      ▼                                          status-conformance judge ──┐
  truth record                                  (public CMS logic +         │
  (held separately,                              stubbed licensed criteria) │
   never seen by                                                            ▼
   the recommender)                              integrity gate  ── suppress + log
      │                                         (independent clinical-      │
      │                                          indication judge)          ▼
      ▼                                                          tiered, provenance-tagged output
   metrics harness  ◀───────────────────────────────────────────  (Tier 1 doc gaps /
   (over-call rate, concordance, calibration,                       Tier 2 indicated workup /
    doc-gap detection, integrity-suppression,                       Tier 3 honest negative)
    patient-protection, equity strata)
```

Every adjudication is snapshotted into a **hash-chained trace** with version + timestamp.

**Retrospective design.** This is a retrospective analysis: *you* know the adjudicated results and
use them to **score**, but the engine still predicts on **decision-time information only** — the
adjudicated status / payer decision / appeal outcome are a **held-out label**, never visible to the
recommender or judges. The leakage firewall stays on; truth is consumed only by the metrics harness.
The recorded *initial* payer decision is used solely for the retrospective **denial-overturn
potential** metric and is never treated as primary truth.

## Synthetic-only posture

- `mode: synthetic` is the only accepted mode; real EHR/claims input is rejected by the contract.
- The recommender (OpenEvidence + dotflows) is a **deterministic stub** behind a swappable
  abstraction — no network, no real OE, no secrets.
- The licensed-criteria conformance check is a **stubbed abstract port** — **no proprietary criteria
  text anywhere** (enforced by `scan-leakage` + a test).
- Real data is blocked until an approved environment + BAA + IRB/QI gate is documented
  (`prereg/PRE_REGISTRATION.md`).

## Run it

```bash
# generate the synthetic corpus (includes deliberately-planted integrity/honest-negative/doc-gap/leakage cases)
python -m admission_engine.cli gen-fixtures --out fixtures/synthetic_cases --n 60

# run the corpus -> per-case artifacts + aggregate metrics + COMBINED REPORT (report.json + report.html)
python -m admission_engine.cli run-corpus --in fixtures/synthetic_cases --out artifacts/run1
#   open artifacts/run1/report.html  (read-only; three sections, every page stamped silent-retrospective)

# run a single case
python -m admission_engine.cli run-case --input fixtures/synthetic_cases/SYN-INPT-0004.json --out artifacts/case1

# scan for proprietary-criteria trademark leakage
python -m admission_engine.cli scan-leakage --path .
```

## Output surface (UX)

Phase 1 is a **silent batch pipeline** (no live/interactive UI). `run-corpus` emits per-case
`cases/<id>.output.json` + `.trace.json`, plus `metrics.json`, `suppression_log.json`,
`rejected_cases.json`, and a **combined report**:

- **`report.json`** — enriched combined report (source of truth)
- **`report.html`** — read-only derived view: ONE document, THREE stacked sections, every page
  stamped *silent retrospective validation — not for live UR use, not patient-facing*:
  1. **Analyst / validation** — over-call rate, concordance, calibration, denial-overturn, equity strata
  2. **Physician-advisor** — per-case tiered output; each doc-gap shows **source tag + supporting
     evidence (which decision-time field backs it) + strength** (clear/moderate/borderline)
  3. **Compliance** — version pins, leakage rejections, integrity suppressions, trace verification,
     no-criteria-text proof

## Tests

```bash
pip install -e ".[dev]"   # or: pip install pytest
pytest -q
python -m py_compile $(find src -name '*.py')
```

The five mandated tests: leakage assertion · judge reproducibility · planted-case integrity
suppression (100%) · willingness-to-say-observation · criteria-leakage scan.

## Open decisions (yours to make)

See `prereg/OPEN_DECISIONS.md` — truth definition, InterQual vs MCG vs both, decision-time
information boundary, first cohort. The engine runs on clearly-marked placeholders until you decide.

## Reuse

`hashing.py` / `trace.py` and the leakage/contract/artifact patterns are reused from the sibling
`ClinClaw/EMEX` project.

## Safety boundaries

No real PHI/claims · no proprietary criteria text · no live/real-time/UR-facing surface · no
autonomous determination · output is for silent validation only, not patient-facing, not orders.
