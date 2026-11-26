from datetime import date, timedelta
from invoicecover.aging_features.contracts import Vintage
from invoicecover.aging_features.engine import (
    aging_bucket,
    aggregate,
    fit_scaler,
    scaled_features,
    support_distance,
)
from invoicecover.aging_features.service import evidence
from invoicecover.invoice_cutoff.contracts import Bill
from invoicecover.repayment_clock.contracts import Settlement

MARK = date(2026, 8, 1)


def vintage(value):
    return Vintage(
        "甲方", "代理", MARK, (0, 0, 0, 0), (value, 100000000.0, 0, 0, 1, 0), 0, 0
    )


def dated(number, days, amount):
    issue = MARK - timedelta(days=80)
    return Bill(
        number, "经销商甲", "代理", issue, MARK - timedelta(days=days), issue, 1, amount
    )


def test_aging_boundaries_are_exclusive():
    # TRAP-23
    assert [aging_bucket(day) for day in (-1, 0, 1, 30, 31, 60, 61)] == [
        0,
        0,
        1,
        1,
        2,
        2,
        3,
    ]


def test_centered_variance_survives_large_offset_and_constants():
    # TRAP-32
    rows = [vintage(1e9 + 0.01), vintage(1e9 - 0.01), vintage(1e9)]
    scale = fit_scaler(rows)
    assert 0.008 < scale.scales[0] < 0.009
    assert scale.scales[1] == 1
    assert scaled_features(rows[2], scale) == (0, 0, 0, 0, 0, 0)


def test_aging_buckets_preserve_outstanding_total():
    rows = [dated("A17", 0, 120), dated("A18", 4, 45), dated("A19", 61, 80)]
    aging = aggregate(rows, [], MARK)[0]
    assert aging.amounts == (120, 45, 0, 80)
    assert sum(aging.amounts) == 245
    assert aging.due_soon == 120


def test_known_already_settled_bill_does_not_mark_debtor_overdue():
    row = dated("A1", 25, 10)
    result = aggregate([row], [Settlement("A1", 0, 0, row.due, ())], MARK)[0]
    assert result.values[:3] == (0, 0, 0)


def test_frozen_scale_ignores_batch_peers():
    # TRAP-53
    base = [vintage(12), vintage(16)]
    scaler = fit_scaler(base)
    first = scaled_features(base[0], scaler)
    crowded = [
        scaled_features(row, scaler) for row in [base[0], vintage(4000), base[1]]
    ]
    assert first == crowded[0]
    assert first[0] == -1


def test_outside_training_range_is_identified():
    scale = fit_scaler([vintage(2), vintage(4)])
    assert support_distance(vintage(3), scale) == 0
    assert support_distance(vintage(10), scale) == 6


def test_evidence_has_all_four_ages():
    report = evidence(aggregate([dated("A", 31, 12)], [], MARK))
    assert report["records"][0]["31–60 天（分）"] == 12
    assert report["records"][0]["61 天以上（分）"] == 0


def test_missing_settlement_and_due_soon_have_separate_values():
    aging = aggregate([dated("A", -11, 10), dated("B", -10, 20)], [], MARK)[0]
    assert aging.amounts[0] == 30
    assert aging.due_soon == 20
