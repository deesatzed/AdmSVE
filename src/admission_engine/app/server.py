"""FastAPI localhost server for the clinician workflow.

Endpoints:
- GET  /                     -> the single-page app
- POST /redact               -> {text} -> {redacted_text, findings}        (step 3, local, no LLM)
- POST /intake               -> {redacted_text, payer, plan_type} -> case_snapshot + handoff (step 2/4)
- POST /ingest-oe            -> {case_snapshot, oe_prose} -> tiered output  (steps 6-7)
- GET  /health               -> liveness + active LLM provider/model

Design: redaction is local and runs first; the LLM (default backend) only ever sees redacted text.
The engine's integrity gate + tiered output wrap the LLM recommender, so the FCA guardrail holds.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..engine import AdmissionStatusEngine
from ..intake import extract_case_snapshot
from ..llm import get_client
from ..oe_prose import parse_oe_prose
from ..recommender.llm_recommender import LLMRecommender
from ..redaction import LayeredRedactor

STATIC_DIR = Path(__file__).resolve().parent / "static"

USE_LIMITATION = (
    "Adjunct decision support — not a status determination, not patient-facing, not an order. "
    "Surfaces existing necessity and independently-indicated workup; status accuracy, never inflation."
)

# Which OE dotflow (resident in OpenEvidence, triggered by a dot command) to run per pathway.
OE_DOT_TRIGGER = ".ed_admit_dc"  # the admit-vs-discharge / status dotflow; reference: dotflows/


def _redactor() -> LayeredRedactor:
    return LayeredRedactor()


def create_app():
    from fastapi import Body, FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(title="Admission Status Engine — Clinician Workflow", version="0.1")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict[str, Any]:
        client = get_client()
        return {"ok": True, "llm_provider": client.provider, "llm_model": client.model}

    @app.post("/redact")
    def redact(body: dict = Body(...)) -> JSONResponse:
        text = str(body.get("text", ""))
        result = _redactor().redact(text)
        return JSONResponse(
            {"redacted_text": result.redacted_text, "findings": result.findings, "clean": result.clean}
        )

    @app.post("/intake")
    def intake(body: dict = Body(...)) -> JSONResponse:
        # Redact first (defense in depth) — the LLM only sees redacted text.
        redacted = _redactor().redact(str(body.get("redacted_text", body.get("text", ""))))
        intake_result = extract_case_snapshot(
            redacted.redacted_text,
            payer=str(body.get("payer", "")),
            plan_type=str(body.get("plan_type", "")),
            case_id=str(body.get("case_id", "CASE-LOCAL")),
            llm=get_client(),
        )
        return JSONResponse(
            {
                "case_snapshot": intake_result.case_snapshot,
                "valid": intake_result.valid,
                "errors": intake_result.errors,
                "llm": {"provider": intake_result.llm_provider, "model": intake_result.llm_model},
                "notes": intake_result.notes,
                "oe_handoff": {
                    "redacted_packet": redacted.redacted_text,
                    "oe_dot_trigger": OE_DOT_TRIGGER,
                    "instruction": (
                        f"Paste the redacted packet into OpenEvidence and run {OE_DOT_TRIGGER}; "
                        "then paste OE's prose answer back here."
                    ),
                },
                "use_limitation": USE_LIMITATION,
            }
        )

    @app.post("/ingest-oe")
    def ingest_oe(body: dict = Body(...)) -> JSONResponse:
        case_snapshot = body.get("case_snapshot") or {}
        oe_prose = str(body.get("oe_prose", ""))
        case_id = case_snapshot.get("case_id", "CASE-LOCAL")

        parsed = parse_oe_prose(oe_prose, case_id=case_id, llm=get_client())
        # LLM recommender is the DEFAULT app backend (built from the parsed OE prose).
        engine = AdmissionStatusEngine(recommender=LLMRecommender(prebuilt=parsed.recommendation))
        outcome = engine.run_case(case_snapshot)

        return JSONResponse(
            {
                "predicted_status": outcome.output.predicted_status,
                "inpatient_likelihood": outcome.output.inpatient_likelihood,
                "output": outcome.output.to_dict(),
                "suppressed_actions": [s.__dict__ for s in outcome.gate_decision.suppressed],
                "oe_parse": {
                    "status": parsed.status,
                    "raw_prose_hash": parsed.raw_prose_hash,
                    "notes": parsed.parse_notes,
                    "llm": {"provider": parsed.llm_provider, "model": parsed.llm_model},
                },
                "use_limitation": USE_LIMITATION,
            }
        )

    return app


def main() -> None:
    import uvicorn

    host = os.environ.get("ADMISSION_ENGINE_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("ADMISSION_ENGINE_APP_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
