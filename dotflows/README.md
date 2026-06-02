# DotFlows — reference for the OE-resident dotflows (PROSE round-trip)

**Important:** the DotFlows live INSIDE OpenEvidence and are invoked there by a dot trigger
(e.g. `.ed_admit_dc`). The app does **not** send a DotFlow prompt to OE. These `.md` files are
**reference copies** documenting what each OE dotflow expects and the **prose** it returns.

## Round-trip is PROSE, not JSON

- The clinician pastes the app's **redacted packet** into OpenEvidence and types the dotflow trigger.
- OE returns a **natural clinical prose** assessment (no JSON expected in either direction).
- The clinician pastes that prose back into the app; `oe_prose/parser.py` maps it to the engine's
  Recommendation shape, preserves the raw prose verbatim (hashed) for audit, and flags
  `needs_review` when it can't parse confidently — it never fabricates structure.

## The dotflow used by the app

| App pathway | OE dot trigger | What OE returns (prose sections the parser looks for) |
|---|---|---|
| Status / admit-vs-discharge | `.ed_admit_dc` | risk framing, documentation gaps, already-indicated workup, honest observation/outpatient statement |

The exact trigger string is configured in `app/server.py` (`OE_DOT_TRIGGER`). Update it to match the
dotflow names provisioned in your OpenEvidence instance.

## Guardrails carried in the prose

The OE dotflows are authored to mirror the engine's invariant: **status accuracy, never status
inflation** — surface documentation of necessity that already exists, surface only independently
clinically-indicated workup, and state plainly when the case is observation/outpatient. The app's
integrity gate independently re-checks any surfaced action regardless of the prose.

## The other `.md` files in this folder

`status_likelihood_recommender.md`, `gap_analysis_review.md`, `documentation_gap_capture.md`,
`clinical_indication_review.md`, `status_conformance_review.md`, `denial_overturn_support.md` are
retained as **authoring references** for the prose sections each role should return. They are not
runtime payloads.
