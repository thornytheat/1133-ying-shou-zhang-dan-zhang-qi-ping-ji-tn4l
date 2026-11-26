from dataclasses import dataclass
from enum import StrEnum


class Term(StrEnum):
    STANDARD = "保留原账期"
    SHORTEN = "建议缩短账期"
    REVIEW = "进入复核"
    WAIT = "待下班复核"


@dataclass(frozen=True)
class ReviewPolicy:
    seats: int
    high_risk: float = 0.72
    medium_risk: float = 0.42
    severe_cents: int = 2800000

    def __post_init__(self):
        if not 0 <= self.seats <= 100 or not 0 < self.medium_risk < self.high_risk < 1:
            raise ValueError("复核额度或风险阈值无效")
        if self.severe_cents < 0:
            raise ValueError("敞口界值不能为负")


@dataclass(frozen=True)
class Decision:
    debtor: str
    term: Term
    reason: str
    risk: float | None
    overdue: int
    exposure: int
    score: float
    seat: int | None


@dataclass(frozen=True)
class QueueSheet:
    policy: ReviewPolicy
    decisions: tuple[Decision, ...]
    open_seats: int

    def __post_init__(self):
        assigned = [row.seat for row in self.decisions if row.seat is not None]
        if (
            sorted(assigned) != list(range(1, len(assigned) + 1))
            or len(assigned) + self.open_seats != self.policy.seats
        ):
            raise ValueError("复核名额与派单日志不一致")
