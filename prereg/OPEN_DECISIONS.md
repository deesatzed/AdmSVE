# Open Decisions — SURFACED, not resolved

Per the goal ("Surface, don't resolve, the open decisions") and handoff §5, the following design
choices are **yours to make**. Each is coded against a clearly-marked placeholder in the source; the
engine runs on the placeholder but **must not be promoted** to a real run until you decide. Do not
let any future session silently resolve these.

---

## 1. Truth definition for `final_adjudicated_status`

- **Where:** `src/admission_engine/contracts/truth.py` → `TRUTH_DEFINITION_PLACEHOLDER`
- **Placeholder:** `post_appeal_adjudicated_status`
- **Candidates:** final UR/physician-advisor determination · post-appeal adjudicated status · payer decision
- **Constraint already enforced in code:** the **initial payer denial is refused as primary truth**
  (`parse_truth` raises if you point the definition at `initial_payer_decision`) — initial payer
  decisions are adversarial and themselves often wrong.
- **Why it matters:** this is the foundation of the entire validity claim.

## 2. InterQual vs MCG vs both (future licensed interface)

- **Where:** `src/admission_engine/judges/criteria_interface.py` → `LicensedCriteriaInterface`
- **Placeholder:** abstract port + `StubbedCriteriaInterface` (`criteria_product = "stubbed_licensed_criteria"`)
- **Status:** no product choice is baked in. No proprietary criteria text exists anywhere. The real
  integration sets `criteria_product` / `criteria_version` and calls the licensed product/API.
- **Why it matters:** licensing path + MA limits on using screening criteria in place of Medicare
  guidelines (handoff §7).

## 3. Decision-time information boundary

- **Where:** `src/admission_engine/contracts/case_snapshot.py` → `DECISION_TIME_BOUNDARY`
- **Placeholder:** `point_of_admission_decision` (vs `full_encounter`)
- **Status:** the leakage contract (`FORBIDDEN_LEAKAGE_KEYS`) fails closed on any post-decision /
  post-adjudication / post-discharge field. If you choose `full_encounter`, the forbidden set must be
  revisited.
- **Why it matters:** validating "would have predicted status" on data that only existed later is
  leakage (handoff Invariant 7).

## 4. First cohort definition

- **Where:** surfaced here; not encoded as a constraint (the generator produces a mixed corpus).
- **Placeholder / leading candidate:** contested short-stay / observation-vs-inpatient cases.
- **Why it matters:** selects what the Phase-1 validation is actually measured on.

---

**Action requested:** confirm or change each of the four. Until then the engine runs only on
synthetic fixtures against the placeholders above.
