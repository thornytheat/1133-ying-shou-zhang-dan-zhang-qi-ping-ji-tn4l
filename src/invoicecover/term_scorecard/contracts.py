from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CalibrationBand:
    maximum_score: float
    loans: int
    events: int

    @property
    def probability(self):
        return self.events / self.loans


@dataclass(frozen=True)
class Scorecard:
    scaler: object
    weights: tuple[float, ...]
    intercept: float
    bands: tuple[CalibrationBand, ...]
    cutoff: date
    train_count: int
    calibration_count: int
    model_id: str


@dataclass(frozen=True)
class DebtorScore:
    debtor: str
    percentile: float
    probability: float | None
    outside_support: float
    state: str
    drivers: tuple[str, ...]


@dataclass(frozen=True)
class ModelFit:
    card: Scorecard
    metrics: dict
    calibration_rows: tuple[dict, ...]
