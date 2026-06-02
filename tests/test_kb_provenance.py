"""KB firewall tests: closed provenance enum, every entry cited, fail-closed loader, determinism."""

import pytest

from admission_engine.kb import KB_VERSION, all_entries, load_kb
from admission_engine.kb.provenance import (
    Citation,
    Provenance,
    coerce_provenance,
    parse_citations,
)
from admission_engine.leakage_scan import CRITERIA_MARKERS

EXPECTED_PROVENANCE = {"cms_public", "peer_reviewed", "public_payer_policy", "derived_concept"}


def test_provenance_enum_is_closed_set():
    assert {p.value for p in Provenance} == EXPECTED_PROVENANCE


def test_provenance_enum_has_no_proprietary_member():
    forbidden = {"proprietary"} | set(CRITERIA_MARKERS)
    for p in Provenance:
        assert p.name.lower() not in forbidden
        assert p.value.lower() not in forbidden


def test_kb_every_entry_has_provenance_and_citation():
    kb = load_kb()
    entries = all_entries(kb)
    assert entries, "KB should not be empty"
    for e in entries:
        assert isinstance(e.provenance, Provenance)
        assert e.citations and len(e.citations) >= 1
        for c in e.citations:
            assert isinstance(c, Citation)
            assert c.ref_id.strip() and c.source.strip()


def test_kb_version_is_pinned():
    assert KB_VERSION
    assert load_kb().version == KB_VERSION


def test_kb_version_bumped_to_v02():
    assert KB_VERSION == "admission_engine.kb.v0.2"


def test_frailty_signals_loaded_and_covered_by_provenance():
    kb = load_kb()
    assert kb.frailty_signals, "frailty signals should load"
    signals = {s.signal for s in kb.frailty_signals}
    assert signals == {
        "adl_dependency",
        "cfs_band",
        "cognitive_status_delirium_risk",
        "recent_admissions",
        "social_support",
    }
    # every frailty signal is in all_entries -> covered by the provenance+citation test
    flat = all_entries(kb)
    for s in kb.frailty_signals:
        assert s in flat
        assert s.provenance in Provenance
        assert s.citations


def test_social_support_requires_necessity_link():
    kb = load_kb()
    social = next(s for s in kb.frailty_signals if s.signal == "social_support")
    assert social.necessity_link_required is True  # the SDOH boundary


def test_kb_load_is_deterministic_singleton():
    a = load_kb()
    b = load_kb()
    assert a is b  # lru_cache
    assert [c.condition for c in a.conditions] == sorted(c.condition for c in a.conditions)


def test_coerce_provenance_rejects_unknown():
    with pytest.raises(ValueError):
        coerce_provenance("proprietary", "ctx")
    with pytest.raises(ValueError):
        coerce_provenance("interqual", "ctx")


def test_parse_citations_requires_at_least_one():
    with pytest.raises(ValueError):
        parse_citations([], "ctx")
    with pytest.raises(ValueError):
        parse_citations(None, "ctx")
    with pytest.raises(ValueError):
        parse_citations([{"ref_id": "", "source": ""}], "ctx")


def test_condition_lookup_matches_and_returns_none():
    kb = load_kb()
    assert kb.condition_for("65yo male with chest pain").condition == "acs_stemi"
    assert kb.condition_for("decompensated heart failure").condition == "adhf"
    assert kb.condition_for("elderly syncope").condition == "syncope"
    assert kb.condition_for("sprained ankle") is None
    assert kb.condition_for("") is None
