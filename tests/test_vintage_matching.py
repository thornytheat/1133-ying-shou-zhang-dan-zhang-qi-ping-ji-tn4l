from datetime import date
from types import SimpleNamespace as Obj
import pytest
from invoicecover.repayment_clock.vintage_matching import (
    elapsed_bucket,
    recovery_records,
    recovery_snapshot,
)

NOW = date(2026, 10, 1)


def example():
    bills = [
        Obj(number="A", channel="直营网", due=date(2026, 7, 30)),
        Obj(number="B", channel="直营网", due=date(2026, 8, 31)),
        Obj(number="C", channel="代理", due=date(2026, 9, 26)),
    ]
    first = [
        Obj(invoice="A", outstanding=11000, paid_on=None),
        Obj(invoice="B", outstanding=4000, paid_on=None),
        Obj(invoice="C", outstanding=200, paid_on=None),
    ]
    current = [
        Obj(invoice="A", outstanding=0, paid_on=date(2026, 9, 27)),
        Obj(invoice="B", outstanding=3000, paid_on=None),
        Obj(invoice="C", outstanding=200, paid_on=None),
    ]
    return bills, first, current


def test_only_anchor_overdue_enters_vintage_denominator():
    results = recovery_snapshot(*example(), NOW, 8)
    assert len(results) == 2
    assert sum(row.balance_at_anchor for row in results) == 15000
    assert sum(row.received for row in results) == 12000


def test_cleared_invoice_records_elapsed_days_from_anchor():
    results = recovery_snapshot(*example(), NOW, 8)
    complete = next(row for row in results if row.fully_settled)
    assert complete.collection_fraction == 1
    assert complete.median_days == 4


def test_newer_records_do_not_change_order_if_input_reversed():
    bills, first, current = example()
    assert recovery_snapshot(bills, first, current, NOW, 8) == recovery_snapshot(
        bills[::-1], first[::-1], current[::-1], NOW, 8
    )


def test_mismatched_snapshots_reject_all_aggregates():
    bills, first, current = example()
    with pytest.raises(ValueError, match="跳过"):
        recovery_snapshot(bills, first, current[1:], NOW, 8)


def test_outstanding_increase_rejects_recovery_snapshot():
    bills, first, current = example()
    current[0].outstanding = 33000
    with pytest.raises(ValueError, match="增加"):
        recovery_snapshot(bills, first, current, NOW, 8)


def test_age_bin_edges_are_distinct():
    assert [elapsed_bucket(day) for day in (7, 8, 30, 31, 60, 61)] == [
        "7 日内",
        "8–30 日",
        "8–30 日",
        "31–60 日",
        "31–60 日",
        "60 日以上",
    ]


def test_duplicate_bill_rejected_even_if_amount_matches():
    bills, first, current = example()
    with pytest.raises(ValueError, match="重复"):
        recovery_snapshot(bills, first + [first[0]], current, NOW, 8)


def test_readback_has_material_fields():
    result = recovery_records(recovery_snapshot(*example(), NOW, 8))
    assert sum(row["已结清"] for row in result) == 1
    assert {row["回款率"] for row in result} == {1, 0.25}
