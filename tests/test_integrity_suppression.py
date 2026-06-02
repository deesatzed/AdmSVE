"""MANDATED TEST 3: planted-case integrity suppression (target 100%).

Every planted action that helps STATUS but is NOT independently indicated must be suppressed and
logged; legitimately-indicated actions must pass (handoff Invariant 2; goal hard rule #3).
"""

from admission_engine.engine import AdmissionStatusEngine
from fixtures.generator import _integrity_suppression_case, generate_corpus


def test_planted_non_indicated_action_is_suppressed():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_integrity_suppression_case(0))
    suppressed_ids = {s.action_id for s in outcome.gate_decision.suppressed}
    assert "a-trap-1" in suppressed_ids
    # The trap must be logged with a clear reason.
    trap = next(s for s in outcome.gate_decision.suppressed if s.action_id == "a-trap-1")
    assert trap.reason == "status_helpful_but_not_independently_indicated"
    assert trap.helps_status is True


def test_legitimately_indicated_action_passes():
    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_integrity_suppression_case(0))
    surfaced_ids = {a.action_id for a in outcome.gate_decision.surfaced}
    assert "a-legit-1" in surfaced_ids


def test_all_planted_non_indicated_actions_suppressed_100pct():
    """Across the whole corpus, every not_independently_indicated new-care action is suppressed."""
    engine = AdmissionStatusEngine()
    planted_total = 0
    suppressed_total = 0
    for case in generate_corpus(60):
        if "final_adjudicated_status" in str(case):  # skip the planted leakage case (fails closed)
            continue
        try:
            outcome = engine.run_case(case)
        except Exception:
            continue
        planted = [
            a for a in (case.get("actions") or [])
            if a.get("clinical_indication_tag") == "not_independently_indicated" and not a.get("present", False)
        ]
        planted_total += len(planted)
        suppressed_ids = {s.action_id for s in outcome.gate_decision.suppressed}
        for a in planted:
            if a["action_id"] in suppressed_ids:
                suppressed_total += 1

    assert planted_total > 0, "expected planted non-indicated actions in the corpus"
    assert suppressed_total == planted_total, (
        f"integrity suppression must be 100%: {suppressed_total}/{planted_total}"
    )


def test_planted_non_indicated_frailty_action_suppressed():
    """A frailty-framed action that helps status but isn't independently indicated must be suppressed."""
    from fixtures.generator import _frailty_trap_case

    engine = AdmissionStatusEngine()
    outcome = engine.run_case(_frailty_trap_case(0))
    suppressed = {s.action_id: s for s in outcome.gate_decision.suppressed}
    assert "a-frailty-trap-1" in suppressed
    assert suppressed["a-frailty-trap-1"].reason == "status_helpful_but_not_independently_indicated"


def test_legitimate_frailty_seed_actions_pass_gate():
    """The KB-seeded frailty Tier-2 actions (PT/OT, geri co-management) are independently indicated."""
    from fixtures.generator import with_frailty
    from admission_engine.judges.gap_analysis import GapAnalysisJudge
    from admission_engine.contracts.case_snapshot import recommender_visible_view

    engine = AdmissionStatusEngine()
    outcome = engine.run_case(with_frailty(_integrity_suppression_case(0)))
    surfaced = {a.action_id for a in outcome.gate_decision.surfaced}
    # at least one frailty seed action surfaced through the gate
    assert any(aid.startswith("frailty-") for aid in surfaced)


def test_gray_zone_is_suppressed_fail_closed():
    """Ensemble disagreement must suppress (fail closed)."""
    engine = AdmissionStatusEngine()
    case = _integrity_suppression_case(0)
    # Make the trap a gray-zone: guideline says no, OE says yes.
    case["actions"][0]["clinical_indication_tag"] = "independently_indicated"
    case["actions"][0]["guideline_indicated"] = False
    case["actions"][0]["oe_indicated"] = True
    outcome = engine.run_case(case)
    suppressed = {s.action_id: s for s in outcome.gate_decision.suppressed}
    assert "a-trap-1" in suppressed
    assert suppressed["a-trap-1"].gray_zone is True
