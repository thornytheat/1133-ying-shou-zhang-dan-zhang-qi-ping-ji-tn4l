from csv import DictReader
from datetime import date
from .contracts import FEATURES, Vintage
from .engine import aggregate, fit_scaler, scaled_features, support_distance


def training_periods(path, prediction_date):
    batches = []
    with path.open(newline="", encoding="utf-8-sig") as source:
        for row in DictReader(source):
            observed = date.fromisoformat(row["observed"])
            outcome = date.fromisoformat(row["outcome"])
            if outcome > prediction_date:
                continue
            if outcome <= observed:
                raise ValueError("账龄目标观测日必须晚于特征日")
            numbers = tuple(
                float(row[f"feature_{index}"]) for index in range(len(FEATURES))
            )
            vintage = Vintage(
                row["debtor"],
                row["channel"],
                observed,
                (0, 0, 0, 0),
                numbers,
                0,
                int(row["late"]),
            )
            batches.append(vintage)
    return tuple(sorted(batches, key=lambda item: (item.as_of, item.debtor)))


def evidence(vintages):
    detail = []
    for row in vintages:
        detail.append(
            {
                "经销商": row.debtor,
                "未到期（分）": row.amounts[0],
                "1–30 天（分）": row.amounts[1],
                "31–60 天（分）": row.amounts[2],
                "61 天以上（分）": row.amounts[3],
                "十日内到期（分）": row.due_soon,
            }
        )
    past_due = sum(sum(row.amounts[1:]) for row in vintages)
    return {
        "title": "账龄特征",
        "summary": f"逾期未结 {past_due / 100:,.2f} 元",
        "records": detail,
    }
