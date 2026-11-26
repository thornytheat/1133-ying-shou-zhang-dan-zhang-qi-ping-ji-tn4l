from dataclasses import dataclass
from datetime import timedelta
from statistics import median


@dataclass(frozen=True)
class RecoverySegment:
    label: str
    invoices: int
    balance_at_anchor: int
    received: int
    collection_fraction: float | None
    fully_settled: int
    median_days: float | None


def elapsed_bucket(days):
    if days <= 7:
        return "7 日内"
    if days <= 30:
        return "8–30 日"
    if days <= 60:
        return "31–60 日"
    return "60 日以上"


def _unique(records):
    result = {row.invoice: row for row in records}
    if len(result) != len(records):
        raise ValueError("快照内账单编号重复")
    return result


def recovery_snapshot(bills, baseline, current, as_of, horizon):
    if horizon < 1 or horizon > 365:
        raise ValueError("催收复盘窗口超出范围")
    baseline_book = _unique(baseline)
    today_book = _unique(current)
    by_number = {bill.number: bill for bill in bills}
    if (
        not by_number.keys() >= baseline_book.keys()
        or not today_book.keys() >= baseline_book.keys()
    ):
        raise ValueError("回款快照跳过历史账单")
    anchor = as_of - timedelta(days=horizon)
    segments = {}
    for number, opening in baseline_book.items():
        bill = by_number[number]
        if bill.due >= anchor or not opening.outstanding:
            continue
        later = today_book[number]
        delta = opening.outstanding - later.outstanding
        if delta < 0:
            raise ValueError("回放期间账面余额异常增加")
        group = (bill.channel, elapsed_bucket((anchor - bill.due).days))
        measures = segments.setdefault(group, [0, 0, 0, []])
        measures[0] += 1
        measures[1] += opening.outstanding
        measures[2] += delta
        if later.paid_on is not None and anchor < later.paid_on <= as_of:
            measures[3].append((later.paid_on - anchor).days)
    report = []
    for (channel, band), (count, gross, recovered, days) in sorted(segments.items()):
        report.append(
            RecoverySegment(
                channel + " / " + band,
                count,
                gross,
                recovered,
                recovered / gross if gross else None,
                len(days),
                median(days) if days else None,
            )
        )
    return tuple(report)


def recovery_records(segments):
    return [
        {
            "催收层": row.label,
            "账单": row.invoices,
            "期初未结（分）": row.balance_at_anchor,
            "期间回款（分）": row.received,
            "回款率": row.collection_fraction,
            "已结清": row.fully_settled,
            "结清用时中位数": row.median_days,
        }
        for row in segments
    ]
