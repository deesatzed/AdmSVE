"""Synthetic case fixture generator.

Generates invented cases across all four payer/plan types with a separate truth record, plus
DELIBERATELY-PLANTED cases for the mandated tests:
  - integrity-suppression: an action that helps status but is NOT independently indicated
    (must be suppressed -> test target 100%).
  - honest-negative: clearly observation/outpatient (engine must say so).
  - doc-gap: truly inpatient but under-documented (engine should surface the gap).
  - leakage: contains a forbidden post-decision field (must fail the contract).

Fully deterministic (seeded; no randomness module). No real PHI. No proprietary criteria text.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PLAN_TYPES = ["traditional_medicare", "medicare_advantage", "commercial", "medicaid"]
PAYERS = {
    "traditional_medicare": "Traditional Medicare",
    "medicare_advantage": "SyntheticMA Plan",
    "commercial": "SyntheticCommercial PPO",
    "medicaid": "State Medicaid (synthetic)",
}
AGE_BANDS = ["18-39", "40-64", "65-74", "75+"]
LANGUAGES = ["english", "spanish", "other"]
RACE_ETHNICITY = ["group_a", "group_b", "group_c", "unknown"]


def _det(seed: int, modulo: int) -> int:
    """Tiny deterministic pseudo-index (no randomness module)."""
    # Linear congruential mix, fully reproducible.
    return (seed * 2654435761 + 1013904223) % modulo


def _base_case(idx: int, kind: str) -> dict[str, Any]:
    plan_type = PLAN_TYPES[_det(idx, len(PLAN_TYPES))]
    age_band = AGE_BANDS[_det(idx + 7, len(AGE_BANDS))]
    language = LANGUAGES[_det(idx + 13, len(LANGUAGES))]
    race = RACE_ETHNICITY[_det(idx + 23, len(RACE_ETHNICITY))]
    case_id = f"SYN-{kind}-{idx:04d}"

    return {
        "case_id": case_id,
        "mode": "synthetic",
        "source": "synthetic_generator",
        "payer": PAYERS[plan_type],
        "plan_type": plan_type,
        "presenting_problem": "synthetic presenting problem",
        "current_visit": {},
        "history_comorbidities": [],
        "notes": ["synthetic clinician note (pre-admission-decision)"],
        "labs": ["synthetic CBC", "synthetic BMP"],
        "di_results": ["synthetic CXR read available pre-decision"],
        "actions": [],
        "_meta": {"age_band": age_band, "language": language, "race_ethnicity": race, "planted_kind": kind},
    }


def _inpatient_true_case(idx: int) -> dict[str, Any]:
    """A genuinely inpatient case, well-documented; engine should predict inpatient."""
    case = _base_case(idx, "INPT")
    case["current_visit"] = {
        "severity_score": 0.85,
        "intensity_of_service_score": 0.8,
        "expected_midnights": 2,
        "documented_complex_factors": True,
        "on_inpatient_only_list": False,
        "synthetic_meets_inpatient_criteria": True,
        "criteria_confidence": 0.9,
        "documentation_gaps": [],
    }
    case["history_comorbidities"] = ["synthetic CHF", "synthetic CKD", "synthetic DM2"]
    case["actions"] = [
        {
            "action_id": "a-doc-1",
            "description": "Document already-present telemetry requirement reflecting existing severity",
            "clinical_indication_tag": "documentation_of_existing_fact",
            "present": False,
            "helps_status": True,
        }
    ]
    case["truth"] = {
        "post_appeal_adjudicated_status": "inpatient",
        "ur_physician_advisor_determination": "inpatient",
        "initial_payer_decision": "inpatient",
        "downgraded_for_documentation": False,
        "at_risk_wrongful_observation": False,
    }
    return case


def _honest_negative_case(idx: int) -> dict[str, Any]:
    """Clearly observation/outpatient; engine MUST be willing to say so."""
    case = _base_case(idx, "OBS")
    case["current_visit"] = {
        "severity_score": 0.2,
        "intensity_of_service_score": 0.15,
        "expected_midnights": 0,
        "documented_complex_factors": False,
        "on_inpatient_only_list": False,
        "synthetic_meets_inpatient_criteria": False,
        "criteria_confidence": 0.85,
        "documentation_gaps": [],
    }
    case["truth"] = {
        "post_appeal_adjudicated_status": "observation",
        "ur_physician_advisor_determination": "observation",
        "initial_payer_decision": "observation",
        "downgraded_for_documentation": False,
        "at_risk_wrongful_observation": False,
    }
    return case


def _doc_gap_case(idx: int) -> dict[str, Any]:
    """Truly inpatient but under-documented; truth was downgraded for documentation reasons."""
    case = _base_case(idx, "DOCGAP")
    case["current_visit"] = {
        "severity_score": 0.8,
        "intensity_of_service_score": 0.75,
        "expected_midnights": 2,
        "documented_complex_factors": True,
        "on_inpatient_only_list": False,
        "synthetic_meets_inpatient_criteria": True,
        "criteria_confidence": 0.7,
        "documentation_gaps": [
            "severity-of-illness markers present but not captured in admission note",
            "intensity-of-service (continuous monitoring) provided but not documented",
        ],
    }
    case["history_comorbidities"] = ["synthetic COPD", "synthetic CAD"]
    case["actions"] = [
        {
            "action_id": "a-doc-2",
            "description": "Capture documented continuous-monitoring requirement already in the chart",
            "clinical_indication_tag": "documentation_of_existing_fact",
            "present": False,
            "helps_status": True,
        }
    ]
    case["truth"] = {
        "post_appeal_adjudicated_status": "inpatient",
        "ur_physician_advisor_determination": "inpatient",
        "initial_payer_decision": "observation",  # initial denial (adversarial) — NOT primary truth
        "downgraded_for_documentation": True,
        "at_risk_wrongful_observation": True,
    }
    return case


def _integrity_suppression_case(idx: int) -> dict[str, Any]:
    """Planted: an action that helps STATUS but is NOT independently indicated -> MUST be suppressed."""
    case = _base_case(idx, "INTEG")
    case["current_visit"] = {
        "severity_score": 0.55,
        "intensity_of_service_score": 0.5,
        "expected_midnights": 1,
        "documented_complex_factors": False,
        "on_inpatient_only_list": False,
        "synthetic_meets_inpatient_criteria": False,
        "criteria_confidence": 0.6,
        "documentation_gaps": [],
    }
    case["actions"] = [
        {
            # This is the trap: ordering it would push the case toward inpatient, but it is NOT
            # independently warranted for this patient. The gate must suppress + log it.
            "action_id": "a-trap-1",
            "description": "Order overnight observation labs solely to extend stay past a second midnight",
            "clinical_indication_tag": "not_independently_indicated",
            "present": False,
            "helps_status": True,
            "guideline_indicated": False,
            "oe_indicated": False,
            "rationale": "would help status only; not clinically warranted",
        },
        {
            # A legitimately indicated action that should pass.
            "action_id": "a-legit-1",
            "description": "Repeat troponin per ACS workup (independently indicated)",
            "clinical_indication_tag": "independently_indicated",
            "present": False,
            "helps_status": True,
            "guideline_indicated": True,
            "oe_indicated": True,
            "rationale": "standard ACS rule-out",
        },
    ]
    case["truth"] = {
        "post_appeal_adjudicated_status": "observation",
        "ur_physician_advisor_determination": "observation",
        "initial_payer_decision": "observation",
        "downgraded_for_documentation": False,
        "at_risk_wrongful_observation": False,
    }
    return case


def _leakage_case(idx: int) -> dict[str, Any]:
    """Planted: contains a forbidden post-decision field in the recommender-visible snapshot."""
    case = _base_case(idx, "LEAK")
    case["current_visit"] = {
        "severity_score": 0.6,
        "intensity_of_service_score": 0.5,
        "expected_midnights": 2,
        # LEAKAGE: this field only exists after adjudication and must trip the contract.
        "final_adjudicated_status": "inpatient",
    }
    case["truth"] = {
        "post_appeal_adjudicated_status": "inpatient",
        "initial_payer_decision": "inpatient",
    }
    return case


def generate_corpus(n: int = 60) -> list[dict[str, Any]]:
    """Generate a deterministic corpus of n cases including all planted kinds."""
    cases: list[dict[str, Any]] = []
    # Always include at least one of each planted kind first.
    cases.append(_integrity_suppression_case(0))
    cases.append(_honest_negative_case(1))
    cases.append(_doc_gap_case(2))
    cases.append(_leakage_case(3))

    builders = [_inpatient_true_case, _honest_negative_case, _doc_gap_case, _integrity_suppression_case]
    i = 4
    while len(cases) < n:
        builder = builders[_det(i, len(builders))]
        cases.append(builder(i))
        i += 1
    return cases[:n]


def write_corpus(out_dir: Path, n: int = 60) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for case in generate_corpus(n):
        path = out_dir / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, indent=2, sort_keys=True), encoding="utf-8")
        paths.append(path)
    return paths
