from datetime import date
from invoicecover.aging_features.contracts import Vintage
from invoicecover.term_scorecard.engine import (
    calibrate,
    diagnostics,
    fit,
    isotonic,
    logistic,
    logistic_fit,
    predict,
    dot,
)
from invoicecover.term_scorecard.service import model_coverage


def observation(day, x, y, code="甲"):
    return Vintage(
        code, "渠道", date(2026, 7, day), (0, 0, 0, 0), (x, 1, 1, 1, 1, 1), 0, y
    )


def fixtures():
    return [
        observation(1, 0, 0),
        observation(2, 1, 0),
        observation(3, 2, 1),
        observation(4, 3, 1),
        observation(12, 0.5, 0),
        observation(13, 1, 1),
        observation(14, 2, 0),
        observation(15, 2.5, 1),
    ]


def test_logistic_extremes_are_finite():
    # TRAP-31
    assert logistic(-1000) == 0
    assert logistic(1000) == 1
    assert logistic(0) == 0.5


def test_degenerate_holdout_reports_undefined_average_precision():
    # TRAP-43
    score = diagnostics([(0.2, 0), (0.4, 0)])
    assert score["average_precision"] is None
    assert score["ece"] > 0


def test_isotonic_repairs_reversed_probability_order():
    # TRAP-44
    points = [(0.1, 0), (0.4, 1), (0.7, 0), (0.9, 1)]
    bands = isotonic(points)
    corrected = [calibrate(bands, digit) for digit, _ in points]
    assert corrected == [0, 0.5, 0.5, 1]
    assert (
        diagnostics(list(zip(corrected, [label for _, label in points])))["ece"]
        < diagnostics(points)["ece"]
    )


def test_calibration_data_never_changes_training_weights():
    # TRAP-42
    split = date(2026, 7, 10)
    model = fit(fixtures(), split).card
    shifted = fit(fixtures() + [observation(22, 1000, 1)], split).card
    assert shifted.scaler == model.scaler
    assert shifted.weights == model.weights
    assert shifted.calibration_count == model.calibration_count + 1


def test_out_of_support_blocks_calibrated_probability():
    card = fit(fixtures(), date(2026, 7, 10)).card
    risk = predict(card, observation(20, 999, None))
    assert risk.probability is None and risk.outside_support > 3
    assert model_coverage([risk]) == {"可评分": 0, "训练分布外": 1}


def test_logistic_regression_orders_linearly_separable_cases():
    coefficients, bias = logistic_fit([(-2,), (-1,), (1,), (2,)], [0, 0, 1, 1], 0.01)
    assert logistic(dot(coefficients, (-2,)) + bias) < 0.15
    assert logistic(dot(coefficients, (2,)) + bias) > 0.85


def test_calibration_parameters_participate_in_model_identity():
    # TRAP-54
    split = date(2026, 7, 10)
    a = fit(fixtures(), split, 0.08).card
    b = fit(fixtures(), split, 0.25).card
    assert a.model_id != b.model_id
    assert a.weights != b.weights


def test_tied_scores_are_order_independent_for_pr_metrics():
    first = [(0.4, 1), (0.4, 0), (0.2, 0)]
    assert diagnostics(first) == diagnostics(first[::-1])
    assert diagnostics(first)["average_precision"] == 0.5
