# Pre-Registration (STUB — numbers intentionally blank)

> Lock this document BEFORE pulling any real record (handoff Invariant 9). This is a Phase-1 stub:
> the structure is here; the **numbers, versions, and thresholds are deliberately left blank** for
> the human to fill in. Do not fill them automatically.

## 1. Version pinning

| Item | Value | Status |
|---|---|---|
| Engine version | `admission_engine.v0.1-synthetic` | placeholder |
| CMS rule effective date (Two-Midnight / OPPS-IPPS year / IPO phase-out) | `__________` | **TO PIN** |
| Licensed criteria product | `__________` (OPEN decision #2) | **TO PIN** |
| Licensed criteria version | `__________` | **TO PIN** |
| Payer/plan routing table version | `__________` | **TO PIN** |

Every adjudication is snapshotted in the hash-chained trace with these values.

## 2. Truth definition (OPEN decision #1)

- Selected truth source: `__________`  (candidates: post-appeal adjudicated status · UR/physician-advisor
  determination · payer decision). **Initial payer denial is NOT permitted as primary truth.**
- Rationale: `__________`

## 3. Decision-time information boundary (OPEN decision #3)

- Boundary: `__________`  (point-of-admission-decision · full-encounter)
- Leakage forbidden-key set reviewed for this boundary: ☐

## 4. Integrity-guardrail tests (locked before running)

- Planted integrity-suppression cases present: ☑ (see fixtures generator)
- Suppression target: **100%** of status-helpful-but-not-independently-indicated new-care actions.
- Leave-OE-out sensitivity analysis pre-registered: ☐ (`leave_oe_out` flag exists)

## 5. Metric definitions

- Status concordance (sensitivity/specificity for true inpatient): defined in `metrics/harness.py`.
- **Over-call rate** (predicted inpatient / truly observation): the tracked failure; reported prominently.
- Documentation-gap detection rate; integrity-suppression count; calibration bins; patient-protection
  rate; equity stratification.
- **Denial-overturn potential** (retrospective): on denied-then-overturned-to-inpatient cases, would
  the engine's surfaced documentation have supported the later-successful appeal? Uses the recorded
  initial payer decision FOR ANALYSIS ONLY — never as primary truth.

## 6. Kill criteria (TO DEFINE)

- Over-call rate above `____` → halt.
- Calibration error above `____` → halt.
- Any criteria-text leakage finding → halt.
- Any decision-time leakage → halt.
- Equity disparity beyond `____` → halt and review.

## 7. Cohort (OPEN decision #4)

- First cohort: `__________`  (leading candidate: contested short-stay / observation-vs-inpatient).

---

**Compliance gate (handoff §8):** no real PHI/claims until an approved environment + BAA + IRB/QI
determination are documented. This stub does not imply any such approval.
