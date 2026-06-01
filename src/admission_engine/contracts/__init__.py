"""Data contracts for the admission-engine Phase-1 harness.

Three contracts:
- case_snapshot: the decision-time information state the recommender is allowed to see, with a
  leakage assertion that fails if any post-decision/adjudication/post-discharge field appears.
- truth: the final adjudicated status (held SEPARATELY from the recommender's input view).
- action_events: orders/treatments with clinical-indication tags.
"""

from .action_events import ActionEvent, parse_action_events
from .case_snapshot import (
    DECISION_TIME_BOUNDARY,
    FORBIDDEN_LEAKAGE_KEYS,
    CaseSnapshotValidation,
    assert_no_leakage,
    find_leakage,
    recommender_visible_view,
    validate_case_snapshot,
)
from .truth import TRUTH_DEFINITION_PLACEHOLDER, AdjudicatedTruth, parse_truth

__all__ = [
    "ActionEvent",
    "parse_action_events",
    "DECISION_TIME_BOUNDARY",
    "FORBIDDEN_LEAKAGE_KEYS",
    "CaseSnapshotValidation",
    "assert_no_leakage",
    "find_leakage",
    "recommender_visible_view",
    "validate_case_snapshot",
    "TRUTH_DEFINITION_PLACEHOLDER",
    "AdjudicatedTruth",
    "parse_truth",
]
