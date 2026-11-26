from dataclasses import replace

from .contracts import CalibrationMode, ProbabilitySource, ReplayReport
from .engine import calibrated_probability, replay

__all__ = ["apply_replay", "calibrated_probability", "channel_records", "evidence", "replay"]


def apply_replay(scores, vintages, report: ReplayReport):
    """把回放选出的校准方式落到当期评分上。

    超出训练范围的户（probability 为 None）保持原评分，不补估概率；
    可评分户按渠道重映射概率，原始线性分与分布外距离不变。
    """
    channels = {row.debtor: row.channel for row in vintages}
    result = []
    for row in scores:
        channel = channels[row.debtor]
        if row.probability is None:
            source = ProbabilitySource.UNSUPPORTED
            updated = row
        else:
            probability = calibrated_probability(row, channel, report)
            if report.mode is CalibrationMode.CHANNEL and channel in report.channel_bands:
                source = ProbabilitySource.CHANNEL
            else:
                source = ProbabilitySource.POOLED
            updated = replace(row, probability=probability)
        result.append((updated, source))
    return tuple(result)


def _round(value):
    return None if value is None else round(value, 6)


def channel_records(report: ReplayReport):
    return [
        {
            "渠道": row.channel,
            "留出户月": row.loans,
            "逾期户月": row.events,
            "正常户月": row.loans - row.events,
            "具备渠道校准资格": row.eligible,
        }
        for row in report.channels
    ]


def evidence(report: ReplayReport, applied):
    comparison = report.comparison
    sources = {
        ProbabilitySource.POOLED: 0,
        ProbabilitySource.CHANNEL: 0,
        ProbabilitySource.UNSUPPORTED: 0,
    }
    for _, source in applied:
        sources[source] += 1
    return {
        "title": "校准回放",
        "summary": (
            f"留出期 {report.holdout_count} 户月，"
            f"采用{report.mode.value}，合格渠道 {len(report.eligible_channels)} 个"
        ),
        "回放窗口": report.split.isoformat(),
        "训练户月": report.train_count,
        "留出户月": report.holdout_count,
        "采用校准": report.mode.value,
        "合格渠道": list(report.eligible_channels),
        "同一批复核户月": comparison.compared_loans,
        "高风险线": comparison.high_risk_line,
        "全体Brier": _round(comparison.pooled_brier),
        "渠道Brier": _round(comparison.channel_brier),
        "Brier门槛": comparison.brier_improved,
        "全体线下漏判": comparison.pooled_missed_events,
        "渠道线下漏判": comparison.channel_missed_events,
        "漏判门槛": comparison.misses_not_increased,
        "门槛同时满足": comparison.gate_passed,
        "概率来源计数": {key.value: value for key, value in sources.items()},
        "回放结论": list(report.reasons),
        "records": channel_records(report),
    }
