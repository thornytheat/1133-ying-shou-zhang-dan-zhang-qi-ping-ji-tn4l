from dataclasses import asdict
from .engine import cash_integrity, drift, group_terms


def evidence(comparison, integrity, vintages, decisions):
    details = [
        {
            "风险下界": row.lower,
            "风险上界": row.upper,
            "历史": row.reference,
            "当前": row.current,
            "变化量": round(row.contribution, 5),
        }
        for row in comparison.bins
    ]
    channel_evidence = [
        {"渠道": channel, "决定": term, "户数": count, "余额（分）": exposure}
        for channel, term, count, exposure in group_terms(vintages, decisions)
    ]
    return {
        "title": "回款复盘",
        "summary": f"{comparison.alarm}，账款差额 {integrity.cents_gap} 分",
        "records": details,
        "cash": asdict(integrity),
        "terms_by_channel": channel_evidence,
        "psi": comparison.population_shift,
        "unsupported": comparison.excluded,
    }


def historical_probabilities(model):
    return tuple(row.probability for row in model.bands for _ in range(row.loans))
