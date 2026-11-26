from datetime import date
from types import SimpleNamespace
import pytest
from invoicecover.collection_vintage.contracts import Alarm
from invoicecover.collection_vintage.engine import cash_integrity, drift, risk_bucket
from invoicecover.collection_vintage.service import evidence
from invoicecover.repayment_clock.contracts import CashBook, Settlement


def test_identical_populations_have_zero_shift():
    same = [0, 0.2, 0.6, 1.0]
    result = drift(same, same)
    assert result.population_shift == 0
    assert result.alarm is Alarm.STABLE


def test_empty_buckets_are_smoothed_but_empty_portfolio_is_explicit():
    moved = drift([0.1] * 60, [0.9] * 60 + [None])
    assert moved.alarm is Alarm.HOLD and moved.excluded == 1
    assert all(block.contribution >= 0 for block in moved.bins)
    assert drift([0.1], [None]).alarm is Alarm.EMPTY
    assert drift([], []).population_shift is None


def test_risk_intervals_have_one_owner_and_include_one():
    assert [risk_bucket(p, 5) for p in (0, 0.1999, 0.2, 0.8, 1)] == [0, 0, 1, 4, 4]
    with pytest.raises(ValueError):
        risk_bucket(float("nan"), 5)


def test_balanced_books_conserve_exact_integer_cents():
    bill = SimpleNamespace(number="A", cents=4005)
    ledger = CashBook((Settlement("A", 4005, 0, None, ()),), ())
    totals = cash_integrity([bill], ledger)
    assert totals.cents_gap == 0 and totals.cents_open == 4005


def test_net_zero_difference_does_not_hide_opposite_row_mismatches():
    bills = [SimpleNamespace(number="A", cents=3), SimpleNamespace(number="B", cents=7)]
    ledger = CashBook(
        (Settlement("A", 2, 0, None, ()), Settlement("B", 8, 0, None, ())), ()
    )
    with pytest.raises(ValueError, match="A, B"):
        cash_integrity(bills, ledger)


def test_missing_invoice_is_detected_before_comparison():
    with pytest.raises(ValueError, match="逐笔匹配"):
        cash_integrity([SimpleNamespace(number="A", cents=4)], CashBook((), ()))


def test_drift_evidence_preserves_excluded_rows_and_balance():
    comparison = drift([0.2], [0.2, None])
    document = evidence(comparison, cash_integrity([], CashBook((), ())), [], [])
    assert document["unsupported"] == 1
    assert sum(row["当前"] for row in document["records"]) == 1
    assert document["cash"]["cents_gap"] == 0


def test_swapping_populations_preserves_symmetric_distance():
    a, b = [0, 0, 0.5, 0.2], [0.3, 0.4, 0.8]
    assert drift(a, b).population_shift == pytest.approx(drift(b, a).population_shift)
