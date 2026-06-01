"""Combined retrospective-validation report (enriched JSON + read-only HTML render).

ONE document, THREE stacked sections, combining all three readers:
  1. Analyst / validation — corpus metrics (over-call rate, concordance, calibration,
     denial-overturn potential, equity strata).
  2. Physician advisor — per-case tiered output (predicted status, documentation gaps with
     supporting-evidence + strength, indicated workup, honest negatives).
  3. Compliance — provenance & guardrails (version pins, leakage rejections, integrity
     suppressions, trace verification, no-criteria-text proof).

EVERY page is stamped: silent retrospective validation, not for live UR use, not patient-facing,
no live determination. JSON is the source of truth; HTML is a derived view.

No proprietary criteria text is ever emitted (the leakage scanner covers generated artifacts).
"""

from __future__ import annotations

import html
from typing import Any

SILENT_STAMP = (
    "SILENT RETROSPECTIVE VALIDATION — not for live UR use · not patient-facing · "
    "no live status determination · status accuracy, never status inflation"
)


def build_corpus_report(
    *,
    metrics: dict[str, Any],
    case_outputs: list[dict[str, Any]],
    suppressions: list[dict[str, Any]],
    rejected_cases: list[dict[str, Any]],
    trace_verification: list[dict[str, Any]],
    version_pins: dict[str, Any],
    criteria_leakage_clean: bool,
) -> dict[str, Any]:
    """Assemble the enriched combined-report JSON (source of truth for the HTML render)."""
    return {
        "schema_version": "admission_engine.combined_report.v0.1",
        "stamp": SILENT_STAMP,
        "section_1_analyst_metrics": metrics,
        "section_2_physician_advisor_cases": case_outputs,
        "section_3_compliance_provenance": {
            "version_pins": version_pins,
            "leakage_rejected_cases": rejected_cases,
            "integrity_suppressions": suppressions,
            "trace_verification": trace_verification,
            "criteria_leakage_clean": criteria_leakage_clean,
        },
    }


# ----------------------------- HTML render ------------------------------------


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _strength_badge(strength: str) -> str:
    color = {"clear": "#1b7837", "moderate": "#b8860b", "borderline": "#a33"}.get(strength, "#555")
    return f'<span class="strength" style="border-color:{color};color:{color}">{_esc(strength)}</span>'


def _render_item(item: dict[str, Any]) -> str:
    evidence = "".join(f"<li><code>{_esc(e)}</code></li>" for e in item.get("supporting_evidence", []))
    return f"""
      <li class="item">
        <div class="item-head">
          <span class="tier">Tier {_esc(item.get('tier'))}</span>
          <span class="src">{_esc(item.get('source_tag'))}</span>
          {_strength_badge(item.get('strength', 'moderate'))}
        </div>
        <div class="item-text">{_esc(item.get('text'))}</div>
        <div class="item-basis"><em>basis:</em> {_esc(item.get('basis'))}</div>
        <div class="item-evidence"><em>supporting evidence (decision-time record):</em><ul>{evidence}</ul></div>
      </li>"""


def _render_case(case: dict[str, Any]) -> str:
    status = case.get("predicted_status", "")
    status_class = "inpatient" if status == "inpatient" else "obs"
    gaps = "".join(_render_item(i) for i in case.get("documentation_gaps", []))
    workup = "".join(_render_item(i) for i in case.get("indicated_pending_workup", []))
    honest = case.get("honest_negative")
    honest_html = _render_item(honest) if honest else "<li class='item muted'>none</li>"
    return f"""
    <details class="case">
      <summary>
        <span class="case-id">{_esc(case.get('case_id'))}</span>
        <span class="status {status_class}">{_esc(status)}</span>
        <span class="likelihood">likelihood {_esc(case.get('inpatient_likelihood'))}</span>
      </summary>
      <h4>Tier 1 — Documentation gaps (capture existing necessity; no new care)</h4>
      <ul class="items">{gaps or "<li class='item muted'>none</li>"}</ul>
      <h4>Tier 2 — Already-indicated pending workup (indicated anyway)</h4>
      <ul class="items">{workup or "<li class='item muted'>none</li>"}</ul>
      <h4>Tier 3 — Honest negative</h4>
      <ul class="items">{honest_html}</ul>
    </details>"""


def _render_metrics(m: dict[str, Any]) -> str:
    conc = m.get("status_concordance", {})
    conf = conc.get("confusion", {})
    docg = m.get("documentation_gap_detection", {})
    dov = m.get("denial_overturn_potential", {})
    pp = m.get("patient_protection", {})
    equity_rows = "".join(
        f"<tr><td>{_esc(k)}</td><td>{_esc(v.get('n'))}</td><td>{_esc(v.get('predicted_inpatient'))}</td>"
        f"<td>{_esc(v.get('over_call_count'))}</td><td>{_esc(v.get('over_call_rate'))}</td></tr>"
        for k, v in (m.get("equity_by_payer", {}) or {}).items()
    )
    calib_rows = "".join(
        f"<tr><td>{_esc(b.get('bin'))}</td><td>{_esc(b.get('count'))}</td>"
        f"<td>{_esc(b.get('mean_predicted_likelihood'))}</td><td>{_esc(b.get('realized_true_inpatient_rate'))}</td></tr>"
        for b in (m.get("calibration_bins", []) or [])
    )
    return f"""
    <p class="headline">OVER-CALL RATE (tracked failure):
       <strong>{_esc(m.get('OVER_CALL_RATE_TRACKED_FAILURE'))}</strong>
       ({_esc(m.get('over_call_count'))} over-calls)</p>
    <table>
      <tr><th>metric</th><th>value</th></tr>
      <tr><td>n scored</td><td>{_esc(m.get('n'))}</td></tr>
      <tr><td>sensitivity (true inpatient)</td><td>{_esc(conc.get('sensitivity_true_inpatient'))}</td></tr>
      <tr><td>specificity (true inpatient)</td><td>{_esc(conc.get('specificity_true_inpatient'))}</td></tr>
      <tr><td>confusion (tp/fp/tn/fn)</td><td>{_esc(conf.get('tp'))}/{_esc(conf.get('fp'))}/{_esc(conf.get('tn'))}/{_esc(conf.get('fn'))}</td></tr>
      <tr><td>doc-gap detection rate</td><td>{_esc(docg.get('detection_rate'))}</td></tr>
      <tr><td>denial-overturn potential rate</td><td>{_esc(dov.get('potential_rate'))} ({_esc(dov.get('overturn_supported_by_engine_docs'))}/{_esc(dov.get('denied_then_overturned'))})</td></tr>
      <tr><td>integrity-suppression count</td><td>{_esc(m.get('integrity_suppression_count'))}</td></tr>
      <tr><td>patient-protection rate</td><td>{_esc(pp.get('protection_rate'))} ({_esc(pp.get('flagged_inpatient_among_at_risk'))}/{_esc(pp.get('at_risk_wrongful_observation'))})</td></tr>
    </table>
    <h4>Calibration</h4>
    <table><tr><th>bin</th><th>count</th><th>mean predicted</th><th>realized true-inpatient</th></tr>{calib_rows}</table>
    <h4>Equity stratification (by plan type)</h4>
    <table><tr><th>plan</th><th>n</th><th>pred inpatient</th><th>over-calls</th><th>over-call rate</th></tr>{equity_rows}</table>"""


def _render_compliance(c: dict[str, Any]) -> str:
    pins = "".join(f"<tr><td>{_esc(k)}</td><td><code>{_esc(v)}</code></td></tr>" for k, v in c.get("version_pins", {}).items())
    rejected = "".join(
        f"<li><code>{_esc(r.get('case_id'))}</code> — {_esc(r.get('error'))}</li>"
        for r in c.get("leakage_rejected_cases", [])
    ) or "<li class='muted'>none</li>"
    supp = "".join(
        f"<li><code>{_esc(s.get('case_id'))}</code> / <code>{_esc(s.get('action_id'))}</code> — "
        f"{_esc(s.get('reason'))}{' (gray-zone)' if s.get('gray_zone') else ''}<br><span class='muted'>{_esc(s.get('description'))}</span></li>"
        for s in c.get("integrity_suppressions", [])
    ) or "<li class='muted'>none</li>"
    traces = c.get("trace_verification", [])
    trace_ok = sum(1 for t in traces if t.get("verified"))
    leak_clean = c.get("criteria_leakage_clean")
    return f"""
    <h4>Version pins (snapshotted per adjudication)</h4>
    <table><tr><th>pin</th><th>value</th></tr>{pins}</table>
    <h4>Leakage — cases rejected fail-closed (decision-time boundary enforced)</h4>
    <ul>{rejected}</ul>
    <h4>Integrity gate — suppressed actions (status-helpful but not independently indicated)</h4>
    <ul class="supp">{supp}</ul>
    <h4>Provenance integrity</h4>
    <p>Trace hash-chain verified: <strong>{trace_ok}/{len(traces)}</strong> cases.</p>
    <p>Proprietary-criteria leakage scan over generated artifacts:
       <strong>{'CLEAN' if leak_clean else 'FINDINGS PRESENT'}</strong>.</p>"""


def render_report_html(report: dict[str, Any]) -> str:
    stamp = _esc(report.get("stamp", SILENT_STAMP))
    metrics_html = _render_metrics(report.get("section_1_analyst_metrics", {}))
    cases_html = "".join(_render_case(c) for c in report.get("section_2_physician_advisor_cases", []))
    compliance_html = _render_compliance(report.get("section_3_compliance_provenance", {}))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Admission Status Engine — Combined Retrospective Report</title>
  <style>
    body {{ font-family: system-ui,-apple-system,BlinkMacSystemFont,sans-serif; margin:0; color:#17202a; }}
    .stamp {{ position:sticky; top:0; background:#7b241c; color:#fff; padding:8px 16px; font-weight:700;
             font-size:13px; letter-spacing:.2px; z-index:10; }}
    main {{ max-width:1040px; margin:0 auto; padding:24px; }}
    h1 {{ margin-top:8px; }}
    section {{ border-top:3px solid #ccd3da; margin-top:28px; padding-top:8px; }}
    section > h2 {{ background:#eef3f8; padding:8px 12px; border-radius:6px; }}
    table {{ border-collapse:collapse; width:100%; margin:8px 0 16px; }}
    th,td {{ border:1px solid #d6dde4; padding:6px 9px; text-align:left; font-size:14px; }}
    th {{ background:#f4f6f8; }}
    code {{ background:#f4f6f8; padding:1px 4px; border-radius:3px; font-size:12px; }}
    .headline {{ font-size:16px; }}
    details.case {{ border:1px solid #d6dde4; border-radius:6px; margin:8px 0; padding:4px 12px; }}
    details.case summary {{ cursor:pointer; display:flex; gap:14px; align-items:center; font-weight:600; }}
    .status.inpatient {{ color:#7b241c; }} .status.obs {{ color:#1b4f72; }}
    .likelihood {{ color:#555; font-weight:400; font-size:13px; }}
    ul.items {{ list-style:none; padding-left:0; }}
    li.item {{ border-left:3px solid #ccd3da; padding:6px 10px; margin:6px 0; }}
    li.item.muted, .muted {{ color:#888; }}
    .item-head {{ display:flex; gap:8px; align-items:center; font-size:12px; }}
    .tier {{ background:#1b4f72; color:#fff; padding:1px 6px; border-radius:4px; }}
    .src {{ background:#e8eef5; padding:1px 6px; border-radius:4px; }}
    .strength {{ border:1px solid; padding:0 6px; border-radius:10px; font-size:11px; font-weight:700; }}
    .item-text {{ font-weight:600; margin:4px 0; }}
    .item-basis,.item-evidence {{ font-size:13px; color:#444; }}
    ul.supp li {{ margin:6px 0; }}
  </style>
</head>
<body>
  <div class="stamp">{stamp}</div>
  <main>
    <h1>Admission Status Engine — Combined Retrospective Validation Report</h1>
    <p class="muted">JSON is the source of truth; this is a derived read-only view. Synthetic-only in Phase 1.</p>

    <section id="analyst">
      <h2>Section 1 — Analyst / Validation metrics</h2>
      {metrics_html}
    </section>

    <section id="physician-advisor">
      <h2>Section 2 — Physician-advisor case-level review</h2>
      <p class="muted">Each case: predicted status + tiered output. Doc-gaps show source tag,
        supporting evidence from the decision-time record, and strength. Capture existing necessity —
        never recommend care to qualify for a higher tier.</p>
      {cases_html}
    </section>

    <section id="compliance">
      <h2>Section 3 — Compliance / Provenance & guardrails</h2>
      {compliance_html}
    </section>
  </main>
</body>
</html>
"""
