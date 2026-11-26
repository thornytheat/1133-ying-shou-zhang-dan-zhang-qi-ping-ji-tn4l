from collections import defaultdict
from math import fsum, isfinite, log
from .contracts import Alarm, CashIntegrity, DriftReport, PerformanceBin


def risk_bucket(probability, buckets):
    if not isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("风险概率须介于 0 和 1")
    return min(int(probability * buckets), buckets - 1)


def drift(reference, current, buckets=5):
    if buckets < 2:
        raise ValueError("风险分箱至少两个")
    base = [0] * buckets
    today = [0] * buckets
    excluded = 0
    for value in reference:
        if value is not None:
            base[risk_bucket(value, buckets)] += 1
    for value in current:
        if value is None:
            excluded += 1
        else:
            today[risk_bucket(value, buckets)] += 1
    if not sum(base) or not sum(today):
        return DriftReport(None, (), Alarm.EMPTY, excluded)
    base_total = sum(base) + 0.5 * buckets
    today_total = sum(today) + 0.5 * buckets
    diagnostics = []
    for index, (historic, actual) in enumerate(zip(base, today, strict=True)):
        ref = (historic + 0.5) / base_total
        now = (actual + 0.5) / today_total
        likelihood = (now - ref) * log(now / ref)
        diagnostics.append(
            PerformanceBin(
                index / buckets, (index + 1) / buckets, historic, actual, likelihood
            )
        )
    psi = fsum(item.contribution for item in diagnostics)
    alarm = Alarm.HOLD if psi >= 0.25 else Alarm.MONITOR if psi >= 0.1 else Alarm.STABLE
    return DriftReport(psi, tuple(diagnostics), alarm, excluded)


def cash_integrity(bills, ledger):
    expected = {row.number: row.cents for row in bills}
    observed = {row.invoice: row for row in ledger.statements}
    if set(expected) != set(observed) or len(observed) != len(ledger.statements):
        raise ValueError("账单与回款记录无法逐笔匹配")
    mismatch = [
        key
        for key, total in expected.items()
        if observed[key].paid + observed[key].outstanding != total
    ]
    if mismatch:
        raise ValueError("逐笔账款不守恒：" + ", ".join(sorted(mismatch)))
    total = sum(expected.values())
    received = sum(statement.paid for statement in observed.values())
    outstanding = sum(statement.outstanding for statement in observed.values())
    return CashIntegrity(
        total, received, outstanding, total - received - outstanding, len(expected)
    )


def group_terms(vintages, decisions):
    channels = {row.debtor: row.channel for row in vintages}
    groups = defaultdict(lambda: [0, 0])
    for row in decisions:
        key = (channels[row.debtor], row.term)
        groups[key][0] += 1
        groups[key][1] += row.exposure
    return tuple(
        (channel, term, count, exposure)
        for (channel, term), (count, exposure) in sorted(groups.items())
    )
