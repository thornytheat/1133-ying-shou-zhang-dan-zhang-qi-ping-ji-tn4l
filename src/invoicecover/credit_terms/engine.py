from dataclasses import replace
from decimal import Decimal
from .contracts import Decision, QueueSheet, Term


def preliminary(aging, score, policy):
    total = sum(aging.amounts)
    overdue = sum(aging.amounts[1:])
    if not total:
        action, why = Term.STANDARD, "余额已结清"
    elif score.probability is None:
        action, why = Term.WAIT, "超出历史观察范围"
    elif aging.amounts[3] >= policy.severe_cents:
        action, why = Term.WAIT, "长期未结超过敞口限额"
    elif score.probability >= policy.high_risk:
        action, why = Term.WAIT, "高逾期概率"
    elif score.probability >= policy.medium_risk and overdue:
        action, why = Term.SHORTEN, "风险与未结账款同时偏高"
    else:
        action, why = Term.STANDARD, "暂不变更"
    return Decision(
        aging.debtor,
        action,
        why,
        score.probability,
        overdue,
        total,
        score.percentile,
        None,
    )


def dispatch(vintages, scores, policy):
    by_debtor = {row.debtor: row for row in scores}
    if len(by_debtor) != len(scores) or set(by_debtor) != {
        row.debtor for row in vintages
    }:
        raise ValueError("评分册与账龄户记录不一致")
    proposed = [preliminary(row, by_debtor[row.debtor], policy) for row in vintages]
    if len(proposed) != len({row.debtor for row in proposed}):
        raise ValueError("每户只能进入一次待审排序")
    queue = sorted(
        (row for row in proposed if row.term == Term.WAIT),
        key=lambda row: (
            row.risk is not None,
            -row.overdue,
            -row.exposure,
            -row.score,
            row.debtor,
        ),
    )
    selected = {row.debtor: index for index, row in enumerate(queue[: policy.seats], 1)}
    final = []
    for row in proposed:
        seat = selected.get(row.debtor)
        final.append(
            replace(row, term=Term.REVIEW, seat=seat) if seat is not None else row
        )
    final.sort(
        key=lambda row: (
            row.seat is None,
            row.seat or 0,
            row.term != Term.WAIT,
            -row.exposure,
            row.debtor,
        )
    )
    return QueueSheet(policy, tuple(final), policy.seats - len(selected))


def expected_exposure(rows):
    supported = sum(
        (
            Decimal(row.exposure) * Decimal(str(row.risk)) / 100
            for row in rows
            if row.risk is not None
        ),
        Decimal(0),
    )
    excluded = sum(row.exposure for row in rows if row.risk is None)
    return supported.quantize(Decimal("0.01")), excluded
