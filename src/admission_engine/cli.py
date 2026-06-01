"""Command-line interface for the admission-engine Phase-1 harness.

Commands:
  gen-fixtures   generate the synthetic corpus
  run-case       run one synthetic case -> tiered output + trace
  run-corpus     run a directory of cases -> per-case artifacts + aggregate metrics
  scan-leakage   scan a tree for proprietary-criteria trademark leakage
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import CMS_RULE_EFFECTIVE_DATE, CRITERIA_INTERFACE_VERSION, ENGINE_VERSION
from .engine import AdmissionStatusEngine
from .leakage_scan import scan_path
from .metrics.harness import compute_metrics
from .report import build_corpus_report, render_report_html


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="admission-engine")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen-fixtures")
    gen.add_argument("--out", required=True, type=Path)
    gen.add_argument("--n", type=int, default=60)

    rc = sub.add_parser("run-case")
    rc.add_argument("--input", required=True, type=Path)
    rc.add_argument("--out", required=True, type=Path)
    rc.add_argument("--leave-oe-out", action="store_true")

    corp = sub.add_parser("run-corpus")
    corp.add_argument("--in", dest="in_dir", required=True, type=Path)
    corp.add_argument("--out", required=True, type=Path)
    corp.add_argument("--leave-oe-out", action="store_true")

    scan = sub.add_parser("scan-leakage")
    scan.add_argument("--path", required=True, type=Path)

    args = parser.parse_args(argv)

    if args.command == "gen-fixtures":
        return _gen_fixtures(args.out, args.n)

    if args.command == "run-case":
        return _run_case(args.input, args.out, args.leave_oe_out)

    if args.command == "run-corpus":
        return _run_corpus(args.in_dir, args.out, args.leave_oe_out)

    if args.command == "scan-leakage":
        findings = scan_path(args.path)
        print(json.dumps({"findings": findings, "clean": not findings}, indent=2))
        return 0 if not findings else 1

    return 2


def _gen_fixtures(out_dir: Path, n: int) -> int:
    # The fixtures package lives at the project root (parent of src/). Add it to sys.path so the
    # generator is importable regardless of CWD.
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from fixtures.generator import write_corpus  # type: ignore

    paths = write_corpus(out_dir, n)
    print(f"Wrote {len(paths)} synthetic cases to {out_dir}")
    return 0


def _run_case(input_path: Path, out_dir: Path, leave_oe_out: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = _load_json(input_path)
    engine = AdmissionStatusEngine(leave_oe_out=leave_oe_out)
    outcome = engine.run_case(payload)

    _write_json(out_dir / f"{outcome.case_id}.output.json", outcome.output.to_dict())
    _write_json(out_dir / f"{outcome.case_id}.trace.json", outcome.trace.render())
    _write_json(
        out_dir / f"{outcome.case_id}.suppression_log.json",
        [s.__dict__ for s in outcome.gate_decision.suppressed],
    )
    ok, msg = outcome.trace.verify()
    print(f"Case {outcome.case_id}: predicted={outcome.output.predicted_status}; trace_verify={ok} ({msg})")
    return 0 if ok else 1


def _run_corpus(in_dir: Path, out_dir: Path, leave_oe_out: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = AdmissionStatusEngine(leave_oe_out=leave_oe_out)
    case_paths = sorted(in_dir.glob("*.json"))
    if not case_paths:
        print(f"No cases found in {in_dir}", file=sys.stderr)
        return 1

    results = []
    skipped_leakage = []
    all_suppressions = []
    case_outputs = []
    trace_verification = []
    per_case_dir = out_dir / "cases"
    per_case_dir.mkdir(parents=True, exist_ok=True)

    for path in case_paths:
        payload = _load_json(path)
        case_id = payload.get("case_id", path.stem)
        try:
            outcome = engine.run_case(payload)
        except Exception as exc:  # leakage/validation cases are expected to fail closed
            skipped_leakage.append({"case_id": case_id, "error": str(exc)})
            continue

        _write_json(per_case_dir / f"{case_id}.output.json", outcome.output.to_dict())
        _write_json(per_case_dir / f"{case_id}.trace.json", outcome.trace.render())
        case_outputs.append(outcome.output.to_dict())
        ok, _ = outcome.trace.verify()
        trace_verification.append({"case_id": case_id, "verified": ok})
        for s in outcome.gate_decision.suppressed:
            all_suppressions.append(s.__dict__)
        if outcome.case_result is not None:
            results.append(outcome.case_result)

    report = compute_metrics(results)
    metrics_dict = report.to_dict()
    _write_json(out_dir / "metrics.json", metrics_dict)
    _write_json(out_dir / "suppression_log.json", all_suppressions)
    _write_json(out_dir / "rejected_cases.json", skipped_leakage)

    # Combined retrospective-validation report (enriched JSON source of truth + HTML render).
    version_pins = {
        "engine_version": ENGINE_VERSION,
        "cms_rule_effective_date": CMS_RULE_EFFECTIVE_DATE,
        "criteria_interface_version": CRITERIA_INTERFACE_VERSION,
    }
    # Scan the just-written per-case artifacts for any proprietary-criteria leakage.
    leakage_findings = scan_path(per_case_dir)
    combined = build_corpus_report(
        metrics=metrics_dict,
        case_outputs=case_outputs,
        suppressions=all_suppressions,
        rejected_cases=skipped_leakage,
        trace_verification=trace_verification,
        version_pins=version_pins,
        criteria_leakage_clean=not leakage_findings,
    )
    _write_json(out_dir / "report.json", combined)
    (out_dir / "report.html").write_text(render_report_html(combined), encoding="utf-8")

    print(f"Ran {len(results)} cases; rejected (fail-closed) {len(skipped_leakage)}.")
    print(
        f"OVER-CALL RATE (tracked failure): {report.over_call_rate:.4f} "
        f"({report.over_call_count} over-calls / {report.tp + report.fp} predicted-inpatient)"
    )
    print(f"Integrity suppressions: {report.total_integrity_suppressions}")
    print(f"Combined report: {out_dir / 'report.html'} (+ report.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
