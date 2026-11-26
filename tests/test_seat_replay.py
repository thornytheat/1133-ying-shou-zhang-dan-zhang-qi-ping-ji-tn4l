from datetime import date
import pytest
from invoicecover.aging_features.contracts import Vintage
from invoicecover.credit_terms.contracts import ReviewPolicy, Term
from invoicecover.credit_terms.seat_replay import (
    compare_limits,
    compare_thresholds,
    review_pressure,
)
from invoicecover.term_scorecard.contracts import DebtorScore


def ensemble():
    stamp = date(2026, 10, 1)
    vintages = [
        Vintage(key, "直供", stamp, (100, age, 0, 0), (0,) * 6, 0)
        for key, age in [("A", 200), ("B", 300), ("C", 5), ("D", 140)]
    ]
    scores = [
        DebtorScore(key, 0.6, p, 0, "可用", ())
        for key, p in [("A", 0.82), ("B", None), ("C", 0.27), ("D", 0.67)]
    ]
    return vintages, scores


def test_limits_are_sorted_and_deduplicated():
    records = compare_limits(*ensemble(), ReviewPolicy(2), [6, 0, 2, 0, 3])
    assert [row.seats for row in records] == [0, 2, 3, 6]


def test_next_manual_seat_preserves_unsupported_priority():
    zero, one, two = compare_limits(*ensemble(), ReviewPolicy(2), [0, 1, 2])
    assert zero.next_customer == "B"
    assert one.next_customer == "A"
    assert one.funds_reviewed == 400
    assert two.funds_reviewed == 700
    assert two.next_customer is None


def test_marginal_exposure_not_accumulated_twice():
    rows = compare_limits(*ensemble(), ReviewPolicy(2), [0, 1, 2, 9])
    assert [row.added_reviewed_cents for row in rows] == [0, 400, 300, 0]
    assert [row.unknown_waiting for row in rows] == [1, 0, 0, 0]


def test_manual_threshold_changes_routing_but_not_ledger_totals():
    first, last = compare_thresholds(*ensemble(), 2, [0.6, 0.9])
    assert first["成案"][Term.WAIT] > last["成案"][Term.WAIT]
    assert first["敞口期望（元）"] == last["敞口期望（元）"]
    assert first["不可估计（分）"] == 400


def test_empty_capacity_set_fails():
    with pytest.raises(ValueError, match="范围"):
        compare_limits(*ensemble(), ReviewPolicy(2), [])


def test_empty_batch_keeps_zero_headroom_with_no_candidate():
    result = review_pressure([], [], ReviewPolicy(2))
    assert all(
        row["等待"] == 0 and row["下一候补"] is None for row in result["额度曲线"]
    )


def test_policy_replay_with_zero_capacity_keeps_all_candidates():
    result = review_pressure(*ensemble(), ReviewPolicy(0))["额度曲线"][0]
    assert result["派发"] == 0 and result["等待"] == 2
