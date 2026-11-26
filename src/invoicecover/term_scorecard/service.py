from .contracts import ModelFit
from .engine import calibrate, diagnostics, fit, isotonic, logistic, predict


def evaluate_book(model: ModelFit, debtors):
    return tuple(predict(model.card, debt) for debt in debtors)


def evidence(model: ModelFit):
    return {
        "title": "账期建模",
        "summary": f"训练 {model.card.train_count} 户月，校准 {model.card.calibration_count} 户月",
        "records": list(model.calibration_rows),
        "metrics": model.metrics,
        "model_id": model.card.model_id,
    }


def model_coverage(scores):
    counts = {"可评分": 0, "训练分布外": 0}
    for row in scores:
        counts[row.state] += 1
    return counts
