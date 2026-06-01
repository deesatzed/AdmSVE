"""Judges (kept separate from the recommender and from each other).

- status_conformance: "does this meet inpatient criteria, and what is missing to DOCUMENT that
  it does?" — public CMS rule logic + a STUBBED licensed-criteria interface (no criteria text).
- clinical_indication: "is this recommended action warranted regardless of billing?" — the
  independent integrity-gate input (OE/guideline ensemble, stubbed). Versioned; leave-OE-out
  supported (handoff Invariant 8).
"""

from .clinical_indication import ClinicalIndicationJudge, IndicationVerdict
from .criteria_interface import CriteriaConformance, LicensedCriteriaInterface, StubbedCriteriaInterface
from .status_conformance import StatusConformanceJudge, StatusVerdict

__all__ = [
    "ClinicalIndicationJudge",
    "IndicationVerdict",
    "CriteriaConformance",
    "LicensedCriteriaInterface",
    "StubbedCriteriaInterface",
    "StatusConformanceJudge",
    "StatusVerdict",
]
