from bisect import bisect_left
from hashlib import sha256
from math import exp, fsum
from .contracts import CalibrationBand, DebtorScore, ModelFit, Scorecard
from ..aging_features.contracts import FEATURES
from ..aging_features.service import fit_scaler, scaled_features, support_distance


def logistic(value):
    if value >= 0:
        return 1 / (1 + exp(-value))
    numerator = exp(value)
    return numerator / (1 + numerator)


def dot(weights, row):
    return fsum(a * b for a, b in zip(weights, row, strict=True))


def logistic_fit(rows, targets, penalty, ticks=240):
    if not rows or len(set(targets)) != 2:
        raise ValueError("评分训练需要同时包含按期与逾期样本")
    features = tuple(zip(*rows, strict=True))
    weights = [0.0] * len(features)
    intercept = 0.0
    for _ in range(ticks):
        error = [
            logistic(intercept + dot(weights, row)) - target
            for row, target in zip(rows, targets, strict=True)
        ]
        updated = []
        for current, column in zip(weights, features, strict=True):
            gradient = fsum(
                difference * value
                for difference, value in zip(error, column, strict=True)
            ) / len(rows)
            updated.append(current - 0.18 * (gradient + penalty * current))
        weights = updated
        intercept -= 0.18 * (fsum(error) / len(rows))
    return tuple(weights), intercept


def isotonic(scored):
    grouped = {}
    for score, outcome in scored:
        count, events = grouped.get(score, (0, 0))
        grouped[score] = (count + 1, events + outcome)
    bands = []
    for score, (count, events) in sorted(grouped.items()):
        bands.append(CalibrationBand(score, count, events))
        while len(bands) > 1 and bands[-2].probability > bands[-1].probability:
            right = bands.pop()
            left = bands.pop()
            bands.append(
                CalibrationBand(
                    right.maximum_score,
                    left.loans + right.loans,
                    left.events + right.events,
                )
            )
    return tuple(bands)


def calibrate(bands, score):
    if not bands:
        return None
    bounds = [band.maximum_score for band in bands]
    return bands[min(len(bounds) - 1, bisect_left(bounds, score))].probability


def diagnostics(predictions):
    if not predictions:
        return {
            "count": 0,
            "brier": None,
            "ece": None,
            "positive": 0,
            "average_precision": None,
        }
    buckets = [[] for _ in range(5)]
    for score, label in predictions:
        buckets[min(int(score * 5), 4)].append((score, label))
    total = len(predictions)
    ece = (
        fsum(abs(fsum(score - label for score, label in bucket)) for bucket in buckets)
        / total
    )
    positive = sum(label for _, label in predictions)
    ranked = sorted(predictions, reverse=True)
    true_positives = 0
    seen = 0
    area = 0
    while seen < total:
        tie = ranked[seen][0]
        end = seen
        hits = 0
        while end < total and ranked[end][0] == tie:
            hits += ranked[end][1]
            end += 1
        true_positives += hits
        area += hits * (true_positives / end)
        seen = end
    return {
        "count": total,
        "brier": fsum((score - label) ** 2 for score, label in predictions) / total,
        "ece": ece,
        "positive": positive,
        "average_precision": area / positive if positive else None,
    }


def fit(population, split, penalty=0.08):
    training = tuple(
        item for item in population if item.as_of < split and item.target is not None
    )
    holdout = tuple(
        item for item in population if item.as_of >= split and item.target is not None
    )
    if not holdout:
        raise ValueError("缺少用于保序校准的独立月份")
    scaler = fit_scaler(training)
    weights, intercept = logistic_fit(
        [scaled_features(item, scaler) for item in training],
        [item.target for item in training],
        penalty,
    )
    predictions = [
        (logistic(intercept + dot(weights, scaled_features(item, scaler))), item.target)
        for item in holdout
    ]
    bands = isotonic(predictions)
    identifier = sha256(
        repr((split, penalty, scaler, weights, intercept, bands)).encode()
    ).hexdigest()[:14]
    model = Scorecard(
        scaler,
        weights,
        intercept,
        bands,
        split,
        len(training),
        len(holdout),
        identifier,
    )
    calibrated = [(calibrate(bands, pred), label) for pred, label in predictions]
    rows = tuple(
        {
            "上限": round(item.maximum_score, 5),
            "样本": item.loans,
            "逾期": item.events,
            "校准概率": round(item.probability, 5),
        }
        for item in bands
    )
    return ModelFit(
        model,
        {"raw": diagnostics(predictions), "calibration": diagnostics(calibrated)},
        rows,
    )


def predict(model, row, limit=3.0):
    vector = scaled_features(row, model.scaler)
    weighted = [
        (name, weight * value)
        for name, weight, value in zip(FEATURES, model.weights, vector, strict=True)
    ]
    drivers = tuple(
        name
        for name, _ in sorted(weighted, key=lambda pair: (-abs(pair[1]), pair[0]))[:2]
    )
    score = logistic(model.intercept + fsum(value for _, value in weighted))
    distance = support_distance(row, model.scaler)
    probability = calibrate(model.bands, score) if distance <= limit else None
    reason = "训练分布外" if probability is None else "可评分"
    return DebtorScore(row.debtor, score, probability, distance, reason, drivers)
