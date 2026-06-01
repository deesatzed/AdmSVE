"""MANDATED TEST 1: leakage assertion.

A planted post-decision/adjudication field in the recommender-visible snapshot must cause the run
to fail closed (handoff Invariant 7).
"""

import pytest

from admission_engine.contracts.case_snapshot import LeakageError, assert_no_leakage, find_leakage
from admission_engine.engine import AdmissionStatusEngine
from fixtures.generator import _leakage_case, _inpatient_true_case


def test_planted_leakage_field_is_detected():
    case = _leakage_case(99)
    leaked = find_leakage({k: v for k, v in case.items() if k not in {"truth", "_meta"}})
    assert any("final_adjudicated_status" in p for p in leaked)


def test_assert_no_leakage_raises_on_planted_case():
    case = _leakage_case(99)
    with pytest.raises(LeakageError):
        assert_no_leakage(case)


def test_engine_fails_closed_on_leakage():
    engine = AdmissionStatusEngine()
    with pytest.raises(Exception):
        engine.run_case(_leakage_case(99))


def test_clean_case_has_no_leakage():
    clean = _inpatient_true_case(5)
    # truth lives in a separate record and is stripped from the recommender view.
    assert assert_no_leakage(clean) is None


def test_truth_record_not_visible_to_recommender():
    from admission_engine.contracts.case_snapshot import recommender_visible_view

    case = _inpatient_true_case(5)
    view = recommender_visible_view(case)
    assert "truth" not in view
