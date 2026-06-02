# Real-Data Readiness Checklist (synthetic → real transition)

> **Purpose.** The engine is validated empirically: real cases with real adjudicated outcomes are
> the truth signal, not pre-verified citations. This checklist is the **gate** between today's
> synthetic-only harness and the first real case. Nothing here touches real data — it enumerates
> what must be true *before* a single real record enters the engine.
>
> **Status today:** synthetic-only by contract. The code rejects real data
> (`contracts/case_snapshot.py`: `mode != "synthetic"` and `source in {real_ehr, real_claims}` both
> fail validation). Do not weaken those checks to run real data — clear the gates below instead.

---

## Gate A — Compliance & data handling (handoff §8) · BLOCKING

Real PHI/claims may not enter until ALL of these are documented and on file:

- [ ] **Approved environment** for PHI/claims (or a BAA'd vendor environment). No real data on a
      developer workstation. — *owner: ____ · evidence link: ____*
- [ ] **BAA** executed covering the data and any vendor in the path. — *owner: ____ · link: ____*
- [ ] **IRB vs QI determination** made and documented. Plausibly QI (utilization/documentation
      performance improvement), but confirm given the data use and any intent to publish. — *owner: ____ · link: ____*
- [ ] **Audit logging** enabled in the approved environment; **role-based access** configured.
- [ ] **No secondary use / no model-training on PHI** confirmed in writing.
- [ ] **Data-use scope** documented: which fields, which cohort, retention, destruction plan.

*Until Gate A clears: synthetic fixtures only. This checklist does not imply any approval exists.*

## Gate B — Methodological lock (handoff Invariant 9, "pre-register before running") · BLOCKING

The four open decisions in `OPEN_DECISIONS.md` MUST be resolved and the `PRE_REGISTRATION.md`
numbers filled BEFORE pulling the first record (locking after seeing data invalidates the claim):

- [ ] **#1 Truth definition** — which adjudicated status is "truth" (leading candidate:
      post-appeal adjudicated status; initial payer denial is code-refused as primary truth). This
      defines *what outcome the modules are scored against* — the validation is only as valid as
      this choice. — *decision: ____*
- [ ] **#3 Decision-time information boundary** — point-of-admission-decision vs full-encounter.
      Sets the leakage firewall for real data. — *decision: ____*
- [ ] **#2 Licensed-criteria choice** — InterQual vs MCG vs both vs public-layer-only (the
      criteria interface stays stubbed until a license + integration path exists). — *decision: ____*
- [ ] **#4 First cohort** — leading candidate: contested short-stay / observation-vs-inpatient
      cases. — *decision: ____*
- [ ] **Version pins** filled in `PRE_REGISTRATION.md`: CMS rule effective-date, criteria
      product+version (if licensed), payer/plan routing table version, engine + KB version
      (currently `admission_engine.kb.v0.3`).
- [ ] **Kill criteria** filled: over-call-rate ceiling, calibration-error ceiling, any
      criteria-leakage finding → halt, any decision-time leakage → halt, equity-disparity threshold.
- [ ] **Metric definitions** locked (the harness already implements: status concordance,
      over-call rate, doc-gap detection, integrity-suppression count, calibration, denial-overturn
      potential, patient-protection, equity strata).

## Gate C — Data-ingestion contract · BLOCKING (build, then gate)

Real EHR/claims exports must be mapped into the case-snapshot contract WITHOUT carrying leakage:

- [ ] **Field mapping** from the real export to the case-snapshot contract
      (`contracts/case_snapshot.py:REQUIRED_TOP_LEVEL`): payer, plan_type, presenting_problem,
      current_visit, history_comorbidities, notes, labs, di_results, actions.
- [ ] **Truth held separately** — the adjudicated status / payer decision / appeal outcome land in
      the truth record (`contracts/truth.py`), NEVER in the recommender-visible snapshot.
- [ ] **Leakage assertion passes on real fields** — every post-decision/adjudication/post-discharge
      field in the real schema is in `FORBIDDEN_LEAKAGE_KEYS` (extend the set to match the real
      export's column names). The run must fail closed on any leak.
- [ ] **PHI redaction** verified on real notes before any text reaches the recommender path. The
      `redaction/` package is the defense-in-depth layer (the approved environment is the PRIMARY
      control): `DeterministicRedactor` (HIPAA-18-style regex floor, std-lib, always on) +
      `LayeredRedactor` + an OPTIONAL `OpenMedRedactor` model backend. The model backend is gated:
      it refuses to load unless `ADMISSION_ENGINE_PHI_ENV_APPROVED=1` and the `redaction-model`
      extra is installed; absent either, redaction degrades to the deterministic floor (fail-safe,
      never fail-open on PHI). The OpenMed models are GENERAL-PII ("not a clinical PHI model" per
      their cards) — recall boosters on the floor, never the sole control. Recalibrate the model
      min-score on a domain eval set before reliance.
- [ ] **Frailty / SDOH fields** (`cfs_score`, `adl_dependencies`, `cognitive_status`,
      `social_support`, `recent_admissions`) mapped if present in the real data; absent → "unknown"
      (honest-negative, never default-to-inpatient).

## Gate D — Code-gate flip (the literal switch) · controlled

Only after Gates A–C are signed off:

- [ ] Decide how real mode is enabled. Today `mode='synthetic'` is hard-required. The flip must be
      **explicit, logged, and reversible** — e.g. a `mode='real'` path that asserts Gate-A evidence
      is present, not a quiet removal of the check. Do NOT delete the synthetic guard; add a gated
      branch beside it.
- [ ] Re-run the full guardrail suite on the real-ingestion adapter against **synthetic** fixtures
      first (the adapter must pass the leakage + invariance tests before it ever sees real data).
- [ ] Confirm the criteria-leakage scan stays clean on any real-derived artifacts/logs.

## Gate E — First real run (retrospective, silent) · the payoff

- [ ] Run the locked, pre-registered cohort retrospectively. Output is **silent** — affects no live
      case (handoff Invariant 5).
- [ ] Read the metric spine per the kill criteria. **Over-call rate is a tracked failure, not a
      win** — a module that inflates status shows up here.
- [ ] **Per-condition breakdown** tells you which of the 25 disease modules earns its keep against
      real outcomes (this is the empirical validation that replaces citation-verification).
- [ ] Snapshot every adjudication (hash-chained trace, version-pinned) for auditability.

---

## What "we'll use real cases" settles — and what it does not

**Settles:** module/threshold validity is now **empirical** — scored against real adjudicated
outcomes, not pre-verified guidelines. `derived_concept` provenance is honest and sufficient; the
modules prove themselves (or don't) in Gate E. No a-priori citation-verification pass is required.

**Does NOT settle (still required above):** the §8 compliance gate (A), the methodological lock and
truth definition (B), the leakage-safe ingestion contract (C). "Use real data" is the goal; these
are the preconditions. A real-case validation is only as valid as the truth definition it scores
against — which is why Gate B is blocking.

---

## One-line status

`Synthetic engine: complete (98 tests green, leakage-clean, over-call 0.0). Real-data gates A–E: OPEN.`
