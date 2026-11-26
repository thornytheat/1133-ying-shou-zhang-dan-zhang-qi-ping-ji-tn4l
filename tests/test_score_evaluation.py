from datetime import date
from dataclasses import replace
import pytest
from invoicecover.aging_features.contracts import Vintage
from invoicecover.term_scorecard.score_evaluation import (
    evaluate_folds,
    reliability_notes,
)


def data():
    return [
        Vintage(
            f"{day}-{index}",
            "经销",
            date(2026, 7, day),
            (0,) * 4,
            (float(index), 0, 0, 1, 0, 0),
            0,
            int(index >= 2),
        )
        for day in range(1, 20)
        for index in range(4)
    ]


def window():
    return (date(2026, 7, 5), date(2026, 7, 10), date(2026, 7, 18))


def test_fold_sizes_and_baselines_are_auditable():
    row = evaluate_folds(data(), [window()])[0]
    assert (row.training, row.calibration, row.validation) == (16, 20, 32)
    assert row.baseline_brier == 0.25 and row.model_brier < 0.25


def test_future_training_rows_do_not_change_completed_replay():
    items = data()
    changed = replace(items[-1], target=0, values=(1000, 0, 0, 1, 0, 0))
    assert evaluate_folds(items, [window()]) == evaluate_folds(
        items + [changed], [window()]
    )


def test_all_unsupported_evaluations_have_distinct_undefined_metrics():
    items = data()
    changed = [
        replace(row, values=(1e8, 0, 0, 1, 0, 0)) if row.as_of >= window()[1] else row
        for row in items
    ]
    record = evaluate_folds(changed, [window()])[0]
    assert record.validation > 0 and record.evaluated == 0
    assert record.baseline_brier is None and record.model_brier is None


def test_window_order_is_contractual():
    with pytest.raises(ValueError, match="递增"):
        evaluate_folds(data(), [window()[::-1]])


def test_replay_returns_comparable_reference_loss():
    row = reliability_notes(evaluate_folds(data(), [window()]))[0]
    assert row["可评分"] == row["留出"]
    assert row["Brier收益"] > 0
    assert row["评估结束日"] == "2026-07-18"


def test_no_future_holdout_returns_empty_support_instead_of_zero_error():
    items = [row for row in data() if row.as_of < window()[1]]
    row = evaluate_folds(items, [window()])[0]
    assert row.validation == 0 and row.average_precision is None
