"""GapAnalysisJudge behavior: Tier-1 only, condition lookup, decision-time only, determinism."""

from admission_engine.contracts.case_snapshot import recommender_visible_view
from admission_engine.judges.gap_analysis import GapAnalysisJudge
from fixtures.generator import _doc_gap_case, _honest_negative_case


def _adhf_case():
    c = _doc_gap_case(2)
    c["presenting_problem"] = "70yo with decompensated heart failure and volume overload"
    c["current_visit"]["clinical_note"] = "requires IV diuretics and telemetry monitoring; hypoxia present"
    return c


def test_gap_items_are_tier1_documentation_of_existing_fact():
    verdict = GapAnalysisJudge().evaluate(recommender_visible_view(_adhf_case()))
    assert verdict.domain_gaps, "expected gap-analysis items on an adhf case"
    for item in verdict.domain_gaps:
        assert item.tier == 1
        assert item.source_tag == "documentation_of_existing_fact"
        assert item.strength in {"clear", "moderate", "borderline"}
        assert item.supporting_evidence  # traceable to a decision-time field


def test_judge_emits_no_new_care():
    """The gap judge must never produce a non-documentation source_tag (no new-care channel)."""
    verdict = GapAnalysisJudge().evaluate(recommender_visible_view(_adhf_case()))
    for item in verdict.domain_gaps:
        assert item.source_tag == "documentation_of_existing_fact"


def test_condition_lookup_by_presenting_problem():
    v = GapAnalysisJudge().evaluate(recommender_visible_view(_adhf_case()))
    assert v.condition_matched == "adhf"


def test_unknown_condition_does_not_raise_or_fabricate():
    c = _honest_negative_case(1)
    c["presenting_problem"] = "minor ankle sprain"
    v = GapAnalysisJudge().evaluate(recommender_visible_view(c))
    assert v.condition_matched is None  # no fabrication


def test_judge_reads_only_case_view_truth_invariant():
    """Presence/absence of truth must not change gap output (judge never sees truth)."""
    case = _adhf_case()
    with_truth_view = recommender_visible_view(case)  # strips truth/_meta already
    a = GapAnalysisJudge().evaluate(with_truth_view)
    b = GapAnalysisJudge().evaluate(with_truth_view)
    assert [i.text for i in a.domain_gaps] == [i.text for i in b.domain_gaps]


def test_judge_is_deterministic():
    case_view = recommender_visible_view(_adhf_case())
    a = GapAnalysisJudge().evaluate(case_view)
    b = GapAnalysisJudge().evaluate(case_view)
    assert [(i.text, i.strength, tuple(i.supporting_evidence)) for i in a.domain_gaps] == [
        (i.text, i.strength, tuple(i.supporting_evidence)) for i in b.domain_gaps
    ]
    assert a.honest_negative_signals == b.honest_negative_signals


# --- frailty pass -----------------------------------------------------------


def _frailty_view():
    from fixtures.generator import with_frailty

    return recommender_visible_view(with_frailty(_honest_negative_case(1)))


def test_frailty_present_yields_tier1_documentation_item():
    v = GapAnalysisJudge().evaluate(_frailty_view())
    frailty_items = [i for i in v.domain_gaps if "frailty" in i.basis]
    assert frailty_items, "expected frailty Tier-1 items when frailty fields present"
    for i in frailty_items:
        assert i.tier == 1
        assert i.source_tag == "documentation_of_existing_fact"
        assert i.supporting_evidence  # traces to the frailty field


def test_frailty_absent_yields_no_fabricated_items():
    v = GapAnalysisJudge().evaluate(recommender_visible_view(_honest_negative_case(1)))
    frailty_items = [i for i in v.domain_gaps if "frailty" in i.basis]
    assert frailty_items == []
    # absent frailty signals appear as honest-negative, never fabricated necessity
    assert any(s.startswith("frailty:") for s in v.honest_negative_signals)


def test_sdoh_without_care_linkage_not_tier1():
    from fixtures.generator import _sdoh_only_case

    v = GapAnalysisJudge().evaluate(recommender_visible_view(_sdoh_only_case(1)))
    social_items = [i for i in v.domain_gaps if "social_support" in i.basis]
    assert social_items == [], "SDOH without documented care-delivery linkage must not be Tier-1"


def test_sdoh_with_care_linkage_becomes_tier1():
    from fixtures.generator import _sdoh_only_case

    case = _sdoh_only_case(1)
    case["current_visit"]["care_delivery_barrier_documented"] = True
    v = GapAnalysisJudge().evaluate(recommender_visible_view(case))
    social_items = [i for i in v.domain_gaps if "social_support" in i.basis]
    assert len(social_items) == 1


def test_frailty_seeds_independently_indicated_actions():
    v = GapAnalysisJudge().evaluate(_frailty_view())
    assert v.seed_actions, "expected Tier-2 seed actions from frailty signals"
    for a in v.seed_actions:
        assert a.is_new_care is True
        assert a.helps_status is False  # surfaced for care, never to qualify status
        assert a.indication_tag == "independently_indicated"
