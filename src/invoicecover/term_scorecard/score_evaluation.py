from dataclasses import dataclass
from math import fsum
from .engine import diagnostics, fit, predict


@dataclass(frozen=True)
class FoldEvidence:
    cutoff: object
    training: int
    calibration: int
    validation: int
    evaluated: int
    baseline_brier: float | None
    model_brier: float | None
    average_precision: float | None
    probability_span: float | None


def evaluate_folds(population, windows):
    result = []
    for calibration, validation, finish in windows:
        if not calibration < validation < finish:
            raise ValueError("训练、拟合和验证日期需要递增")
        reference = [record for record in population if record.as_of < validation]
        held = [
            record
            for record in population
            if validation <= record.as_of < finish and record.target is not None
        ]
        fitted = fit(reference, calibration)
        past = [
            record.target
            for record in reference
            if record.as_of < calibration and record.target is not None
        ]
        baseline = fsum(past) / len(past)
        pairs = [
            (predict(fitted.card, record).probability, record.target) for record in held
        ]
        supported = [(prob, outcome) for prob, outcome in pairs if prob is not None]
        model = diagnostics(supported)
        base = diagnostics([(baseline, outcome) for _, outcome in supported])
        values = [p for p, _ in supported]
        span = max(values) - min(values) if values else None
        result.append(
            FoldEvidence(
                finish,
                fitted.card.train_count,
                fitted.card.calibration_count,
                len(held),
                len(values),
                base["brier"],
                model["brier"],
                model["average_precision"],
                span,
            )
        )
    return tuple(result)


def reliability_notes(rows):
    panel = []
    for row in rows:
        gain = (
            row.baseline_brier - row.model_brier
            if row.baseline_brier is not None and row.model_brier is not None
            else None
        )
        panel.append(
            {
                "评估结束日": row.cutoff.isoformat(),
                "训练": row.training,
                "校准": row.calibration,
                "留出": row.validation,
                "可评分": row.evaluated,
                "原始率Brier": row.baseline_brier,
                "线性模型Brier": row.model_brier,
                "Brier收益": gain,
                "AP": row.average_precision,
                "概率跨度": row.probability_span,
            }
        )
    return panel
