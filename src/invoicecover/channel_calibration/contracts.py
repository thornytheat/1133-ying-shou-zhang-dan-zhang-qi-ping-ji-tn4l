from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class CalibrationMode(StrEnum):
    POOLED = "全体校准"
    CHANNEL = "渠道校准"


class ProbabilitySource(StrEnum):
    POOLED = "全体校准概率"
    CHANNEL = "渠道校准概率"
    UNSUPPORTED = "分布外不补估"


@dataclass(frozen=True)
class ChannelHoldout:
    """单渠道在留出期上的回放拟合证据。"""

    channel: str
    loans: int
    events: int
    eligible: bool
    bands: tuple[object, ...] = field(default_factory=tuple, compare=False)


@dataclass(frozen=True)
class CalibrationComparison:
    """同一批复核户月上的两种校准对比。"""

    compared_loans: int
    pooled_brier: float | None
    channel_brier: float | None
    pooled_missed_events: int | None
    channel_missed_events: int | None
    high_risk_line: float
    brier_improved: bool
    misses_not_increased: bool

    @property
    def gate_passed(self):
        return self.brier_improved and self.misses_not_increased


@dataclass(frozen=True)
class ReplayReport:
    """历史回放结论：拟合窗口、合格渠道与采用门槛。"""

    split: date
    train_count: int
    holdout_count: int
    mode: CalibrationMode
    eligible_channels: tuple[str, ...]
    channels: tuple[ChannelHoldout, ...]
    comparison: CalibrationComparison
    reasons: tuple[str, ...]
    pooled_bands: tuple[object, ...] = field(default_factory=tuple, compare=False)
    channel_bands: dict = field(default_factory=dict, compare=False)
