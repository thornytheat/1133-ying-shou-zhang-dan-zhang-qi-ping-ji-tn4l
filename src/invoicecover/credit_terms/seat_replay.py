from dataclasses import dataclass
from .contracts import QueueSheet, ReviewPolicy, Term
from .engine import dispatch, expected_exposure


@dataclass(frozen=True)
class CapacityPoint:
    seats: int
    placed: int
    waiting: int
    funds_reviewed: int
    funds_waiting: int
    unknown_waiting: int
    next_customer: str | None
    added_reviewed_cents: int


def compare_limits(vintages, scores, base, limits):
    ordered = sorted(set(limits))
    if not ordered or min(ordered) < 0 or max(ordered) > 100:
        raise ValueError("额度比较范围无效")
    previous = set()
    points = []
    for limit in ordered:
        policy = ReviewPolicy(
            limit, base.high_risk, base.medium_risk, base.severe_cents
        )
        board = dispatch(vintages, scores, policy)
        active = [row for row in board.decisions if row.term == Term.REVIEW]
        pending = [row for row in board.decisions if row.term == Term.WAIT]
        identities = {row.debtor for row in active}
        if not previous <= identities:
            raise ValueError("追加席位导致原复核户消失")
        tail = min(
            pending,
            key=lambda row: (
                row.risk is not None,
                -row.overdue,
                -row.exposure,
                -row.score,
                row.debtor,
            ),
            default=None,
        )
        points.append(
            CapacityPoint(
                limit,
                len(active),
                len(pending),
                sum(row.exposure for row in active),
                sum(row.exposure for row in pending),
                sum(row.risk is None for row in pending),
                tail.debtor if tail else None,
                sum(row.exposure for row in active if row.debtor not in previous),
            )
        )
        previous = identities
    return tuple(points)


def compare_thresholds(vintages, scores, seats, high_values):
    if any(not 0.42 < value < 1 for value in high_values):
        raise ValueError("人工线必须超过缩短账期阈值")
    result = []
    for value in sorted(set(high_values)):
        queue = dispatch(vintages, scores, ReviewPolicy(seats, high_risk=value))
        terms = {
            name.value: sum(row.term == name for row in queue.decisions)
            for name in Term
        }
        exposure, excluded = expected_exposure(queue.decisions)
        result.append(
            {
                "人工阈值": value,
                "成案": terms,
                "敞口期望（元）": float(exposure),
                "不可估计（分）": excluded,
            }
        )
    return result


def review_pressure(vintages, scores, policy):
    points = compare_limits(
        vintages, scores, policy, [0, 1, policy.seats, max(policy.seats, 12), 100]
    )
    records = [
        {
            "额度": point.seats,
            "派发": point.placed,
            "等待": point.waiting,
            "复核敞口（分）": point.funds_reviewed,
            "未复核敞口（分）": point.funds_waiting,
            "未评分等待数": point.unknown_waiting,
            "增量复核（分）": point.added_reviewed_cents,
            "下一候补": point.next_customer,
        }
        for point in points
    ]
    return {
        "额度曲线": records,
        "阈值清单": compare_thresholds(
            vintages, scores, policy.seats, [0.6, 0.72, 0.82]
        ),
    }
