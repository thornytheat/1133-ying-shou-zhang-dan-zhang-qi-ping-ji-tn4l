from datetime import date
import pytest
from invoicecover.aging_features.contracts import Vintage
from invoicecover.credit_terms.contracts import ReviewPolicy, Term
from invoicecover.credit_terms.engine import dispatch, expected_exposure
from invoicecover.credit_terms.service import evidence
from invoicecover.term_scorecard.contracts import DebtorScore


def vintage(name, age=200):
    return Vintage(
        name, "商贸", date(2026, 8, 1), (100, 0, 0, age), (0, 0, 0, 0, 0, 0), 0
    )


def risk(name, probability):
    return DebtorScore(name, 0.55, probability, 0, "可评分", ())


def test_competing_rules_keep_conservative_priority_independent_of_input_order():
    # TRAP-19
    policy = ReviewPolicy(1, severe_cents=180)
    a = vintage("甲")
    b = vintage("乙", 150)
    scores = [risk("甲", 0.9), risk("乙", 0.3)]
    first = dispatch([a, b], scores, policy)
    assert dispatch([b, a], scores[::-1], policy) == first
    assert first.decisions[0].reason == "长期未结超过敞口限额"


def test_unknown_model_score_gets_manual_seat_ahead_of_known():
    sheet = dispatch(
        [vintage("高分"), vintage("未知")],
        [risk("高分", 0.99), risk("未知", None)],
        ReviewPolicy(1),
    )
    assert sheet.decisions[0].debtor == "未知"
    assert sheet.decisions[0].seat == 1
    assert sheet.decisions[1].term == Term.WAIT


def test_medium_risk_shortens_terms_without_spending_a_seat():
    sheet = dispatch([vintage("中等")], [risk("中等", 0.60)], ReviewPolicy(2))
    assert sheet.decisions[0].term == Term.SHORTEN
    assert sheet.open_seats == 2


def test_zero_capacity_keeps_work_visible():
    sheet = dispatch([vintage("高分")], [risk("高分", 0.99)], ReviewPolicy(0))
    assert sheet.open_seats == 0
    assert sheet.decisions[0].term == Term.WAIT


def test_unmatched_score_rejects_entire_batch():
    with pytest.raises(ValueError, match="不一致"):
        dispatch([vintage("甲")], [risk("乙", 0.5)], ReviewPolicy(1))


def test_exact_threshold_enqueues_customer():
    sheet = dispatch([vintage("甲")], [risk("甲", 0.72)], ReviewPolicy(1))
    assert sheet.decisions[0].term == Term.REVIEW


def test_exposure_exclusion_is_reported_separately():
    sheet = dispatch(
        [vintage("甲"), vintage("乙", 50)],
        [risk("甲", 0.5), risk("乙", None)],
        ReviewPolicy(2),
    )
    expected, unsupported = expected_exposure(sheet.decisions)
    assert str(expected) == "1.50"
    assert unsupported == 150
    assert evidence(sheet)["out_of_support_cents"] == 150


def test_invalid_threshold_order_is_rejected():
    with pytest.raises(ValueError):
        ReviewPolicy(2, high_risk=0.4, medium_risk=0.6)
