"""Payer-routing tests: plan type selects the applicable standard + audit posture."""

import pytest

from admission_engine.payer_routing import route


def test_traditional_medicare_has_presumption():
    r = route("traditional_medicare")
    assert r.applies_two_midnight_benchmark is True
    assert r.applies_two_midnight_presumption is True
    assert r.may_audit_any_length is False
    assert r.applies_ipo_list is True


def test_medicare_advantage_no_presumption_audits_any_length():
    r = route("medicare_advantage")
    assert r.applies_two_midnight_benchmark is True
    assert r.applies_two_midnight_presumption is False  # CMS-4201-F
    assert r.may_audit_any_length is True
    assert r.applies_ipo_list is True


def test_commercial_and_medicaid_route_to_plan_specific():
    for pt in ("commercial", "medicaid"):
        r = route(pt)
        assert r.applies_two_midnight_presumption is False
        assert "plan_specific" in r.audit_posture or "route_to_applicable" in r.applicable_standard


def test_unknown_plan_type_raises():
    with pytest.raises(ValueError):
        route("nonsense_plan")
