from collections import Counter, defaultdict
from math import fsum, log1p, sqrt
from .contracts import FeatureScaler, Vintage


def aging_bucket(days):
    if days <= 0:
        return 0
    if days <= 30:
        return 1
    if days <= 60:
        return 2
    return 3


def aggregate(bills, statements, as_of, targets=None):
    settlement = {row.invoice: row.outstanding for row in statements}
    groups = defaultdict(list)
    for bill in bills:
        if bill.posted <= as_of and bill.issued <= as_of:
            groups[bill.debtor].append(bill)
    result = []
    for debtor, group in sorted(groups.items()):
        original = sum(row.cents for row in group)
        outstanding = 0
        oldest = 0
        due_soon = 0
        bins = [0] * 4
        for bill in group:
            remaining = settlement.get(bill.number, bill.cents)
            if not 0 <= remaining <= bill.cents:
                raise ValueError("未结金额大于账款或小于零")
            days = (as_of - bill.due).days
            bins[aging_bucket(days)] += remaining
            outstanding += remaining
            if remaining:
                oldest = max(oldest, days)
            if -10 <= days <= 0:
                due_soon += remaining
        channel = sorted(
            Counter(row.channel for row in group).items(),
            key=lambda row: (-row[1], row[0]),
        )[0][0]
        values = (
            outstanding / original,
            sum(bins[1:]) / original,
            float(oldest),
            max((as_of - row.issued).days for row in group),
            float(len(group)),
            log1p(outstanding / 100),
        )
        result.append(
            Vintage(
                debtor,
                channel,
                as_of,
                tuple(bins),
                values,
                due_soon,
                None if targets is None else targets.get(debtor),
            )
        )
    return tuple(result)


def fit_scaler(vintages):
    if not vintages:
        raise ValueError("缺少训练样本")
    observations = tuple(zip(*(row.values for row in vintages), strict=True))
    mean = tuple(fsum(col) / len(col) for col in observations)
    sigma = tuple(
        sqrt(fsum((value - center) ** 2 for value in col) / len(col))
        for col, center in zip(observations, mean, strict=True)
    )
    return FeatureScaler(
        mean,
        tuple(value if value >= 1e-9 else 1 for value in sigma),
        tuple(map(min, observations)),
        tuple(map(max, observations)),
    )


def scaled_features(row, scaler):
    return tuple(
        (value - center) / scale
        for value, center, scale in zip(
            row.values, scaler.center, scaler.scales, strict=True
        )
    )


def support_distance(row, scaler):
    outside = [
        max(low - value, 0, value - high) / scale
        for value, low, high, scale in zip(
            row.values, scaler.minimum, scaler.maximum, scaler.scales, strict=True
        )
    ]
    return sqrt(fsum(distance**2 for distance in outside))
