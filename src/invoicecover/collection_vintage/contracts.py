from dataclasses import dataclass
from enum import StrEnum


class Alarm(StrEnum):
    STABLE = "稳定"
    MONITOR = "观察"
    HOLD = "暂停自动执行"
    EMPTY = "无可比样本"


@dataclass(frozen=True)
class PerformanceBin:
    lower: float
    upper: float
    reference: int
    current: int
    contribution: float


@dataclass(frozen=True)
class DriftReport:
    population_shift: float | None
    bins: tuple[PerformanceBin, ...]
    alarm: Alarm
    excluded: int


@dataclass(frozen=True)
class CashIntegrity:
    cents_in: int
    cents_paid: int
    cents_open: int
    cents_gap: int
    invoice_count: int
