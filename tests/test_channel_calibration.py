from datetime import date

import pytest

from invoicecover.aging_features.contracts import Vintage
from invoicecover.channel_calibration import service
from invoicecover.channel_calibration.contracts import (
    CalibrationMode,
    ProbabilitySource,
)
from invoicecover.channel_calibration.diagnostics import report as report_diagnostics
from invoicecover.channel_calibration.engine import calibrated_probability, replay
from invoicecover.term_scorecard.contracts import DebtorScore

SPLIT = date(2026, 6, 1)
CHANNELS = ("甲渠道", "乙渠道")


def observation(day, channel, x, target, code=None):
    return Vintage(
        code or f"{channel}-{day}",
        channel,
        date(2026, day // 100, day % 100),
        (0, 0, 0, 0),
        (float(x), 1.0, 1.0, 1.0, 1.0, 1.0),
        0,
        target,
    )


def population():
    # 训练段：两个渠道同分布，均同时含逾期与正常，线性可分且方向一致。
    rows = []
    for month in (1, 2, 3, 4, 5):
        for channel in CHANNELS:
            rows.extend(
                [
                    observation(month * 100 + 1, channel, 0.0, 0),
                    observation(month * 100 + 2, channel, 1.0, 0),
                    observation(month * 100 + 3, channel, 2.0, 1),
                    observation(month * 100 + 4, channel, 3.0, 1),
                ]
            )
    # 留出段：同一原始分在两渠道结论相反（样本分布偏移），
    # 全体保序被迫折中，分渠道校准仍贴合各自逾期率；两渠道均含两类标签。
    rows.extend(
        [
            observation(601, "甲渠道", 0.2, 0),
            observation(602, "甲渠道", 2.0, 1),
            observation(603, "甲渠道", 3.2, 1),
            observation(605, "乙渠道", 0.2, 0),
            observation(606, "乙渠道", 2.0, 0),
            observation(607, "乙渠道", 3.2, 1),
        ]
    )
    return rows


def score(debtor, probability=0.5, percentile=0.6, outside=0.0, state="可评分"):
    return DebtorScore(debtor, percentile, probability, outside, state, ())


def vintage(debtor, channel):
    return Vintage(
        debtor, channel, SPLIT, (0, 0, 0, 0), (0.1,) * 6, 0, None
    )


def test_replay_only_uses_matured_outcomes_before_holdout_start():
    report = replay(population(), SPLIT)
    assert report.train_count == 40
    assert report.holdout_count == 6
    assert report.split == SPLIT
    # 追加留出期之后才成熟的户月，不进入训练口径，杜绝未来信息。
    shifted = population() + [observation(801, "甲渠道", 9.0, 1)]
    later = replay(shifted, SPLIT)
    assert later.train_count == report.train_count
    assert later.holdout_count == report.holdout_count + 1


def test_channel_requires_both_classes_in_holdout():
    rows = population()
    rows.extend(
        [
            observation(701, "丙渠道", 0.2, 0),
            observation(702, "丙渠道", 0.4, 0),
        ]
    )
    report = replay(rows, SPLIT)
    single_class = next(row for row in report.channels if row.channel == "丙渠道")
    assert single_class.eligible is False
    assert "丙渠道" not in report.eligible_channels
    # 单类渠道不参与同批比较，比较集仍是甲乙两渠道的 6 个户月。
    assert report.comparison.compared_loans == 6


def test_channel_calibration_adopted_when_both_gates_pass():
    report = replay(population(), SPLIT, high_risk_line=0.72)
    comparison = report.comparison
    assert comparison.channel_brier < comparison.pooled_brier
    assert comparison.brier_improved is True
    assert comparison.channel_missed_events <= comparison.pooled_missed_events
    assert comparison.misses_not_increased is True
    assert comparison.gate_passed is True
    assert report.mode is CalibrationMode.CHANNEL


def test_pooled_fallback_when_brier_does_not_improve(monkeypatch):
    from invoicecover.channel_calibration import engine

    original = engine._brier
    calls = {"count": 0}

    def patched(pairs):
        calls["count"] += 1
        if not pairs:
            return None
        # 第二次调用对应渠道校准，定向恶化其平方误差。
        return original(pairs) + (1.0 if calls["count"] % 2 == 0 else 0.0)

    monkeypatch.setattr(engine, "_brier", patched)
    report = replay(population(), SPLIT)
    assert report.comparison.brier_improved is False
    assert report.comparison.gate_passed is False
    assert report.mode is CalibrationMode.POOLED
    assert any("沿用全体校准" in note for note in report.reasons)


def test_pooled_fallback_when_missed_events_increase(monkeypatch):
    from invoicecover.channel_calibration import engine

    original = engine._missed_events
    calls = {"count": 0}

    def patched(pairs, line):
        calls["count"] += 1
        value = original(pairs, line)
        # 第二次调用对应渠道校准，定向构造漏判高于全体。
        return value + 2 if calls["count"] % 2 == 0 else value

    monkeypatch.setattr(engine, "_missed_events", patched)
    report = replay(population(), SPLIT)
    assert report.comparison.brier_improved is True
    assert report.comparison.misses_not_increased is False
    assert report.comparison.gate_passed is False
    assert report.mode is CalibrationMode.POOLED


def test_no_eligible_channel_forces_pooled_calibration():
    rows = population()
    # 把乙渠道留出标签全部改成正常，乙渠道只剩单类，仅甲渠道保留资格。
    only_jia = [
        row
        for row in rows
        if row.channel != "乙渠道" or row.as_of < SPLIT
    ] + [
        observation(605, "乙渠道", 0.2, 0),
        observation(606, "乙渠道", 2.0, 0),
        observation(607, "乙渠道", 3.2, 0),
    ]
    report = replay(only_jia, SPLIT)
    assert report.eligible_channels == ("甲渠道",)
    assert report.comparison.compared_loans == 3

    # 再把甲渠道留出逾期结论也改成正常，两个渠道都失去资格。
    neither = [
        row
        for row in only_jia
        if row.channel != "甲渠道" or row.as_of < SPLIT
    ] + [
        observation(601, "甲渠道", 0.2, 0),
        observation(602, "甲渠道", 2.0, 0),
        observation(603, "甲渠道", 3.2, 0),
    ]
    report_two = replay(neither, SPLIT)
    assert report_two.eligible_channels == ()
    assert report_two.comparison.compared_loans == 0
    assert report_two.comparison.gate_passed is False
    assert report_two.mode is CalibrationMode.POOLED
    assert any("不具备分渠道校准条件" in note for note in report_two.reasons)


def test_replay_requires_two_matured_segments():
    only_training = [row for row in population() if row.as_of < SPLIT]
    with pytest.raises(ValueError, match="训练与留出"):
        replay(only_training, SPLIT)


def test_apply_replay_remaps_supported_and_keeps_out_of_support():
    report = replay(population(), SPLIT)
    assert report.mode is CalibrationMode.CHANNEL
    accounts = [vintage("户一", "甲渠道"), vintage("户二", "乙渠道")]
    scores = [
        score("户一", probability=0.8),
        score("户二", probability=None, outside=4.2, state="训练分布外"),
    ]
    applied = service.apply_replay(scores, accounts, report)
    first, first_source = applied[0]
    second, second_source = applied[1]
    assert first_source is ProbabilitySource.CHANNEL
    assert first.probability == calibrated_probability(scores[0], "甲渠道", report)
    assert first.percentile == scores[0].percentile
    # 超出训练范围的户不补估概率，沿用原处置输入。
    assert second_source is ProbabilitySource.UNSUPPORTED
    assert second.probability is None
    assert second.outside_support == 4.2
    assert second.state == "训练分布外"


def test_apply_replay_uses_pooled_when_report_falls_back(monkeypatch):
    from invoicecover.channel_calibration import engine

    original = engine._brier
    calls = {"count": 0}

    def patched(pairs):
        calls["count"] += 1
        if not pairs:
            return None
        return original(pairs) + (1.0 if calls["count"] % 2 == 0 else 0.0)

    monkeypatch.setattr(engine, "_brier", patched)
    report = replay(population(), SPLIT)
    accounts = [vintage("户一", "甲渠道")]
    applied = service.apply_replay([score("户一")], accounts, report)
    _, source = applied[0]
    assert source is ProbabilitySource.POOLED


def test_apply_replay_unknown_channel_uses_pooled_bands():
    report = replay(population(), SPLIT)
    accounts = [vintage("新户", "丁渠道")]
    applied = service.apply_replay([score("新户")], accounts, report)
    updated, source = applied[0]
    assert source is ProbabilitySource.POOLED
    assert updated.probability == calibrated_probability(score("新户"), "丁渠道", report)


def test_evidence_rounds_metrics_and_conserves_sources():
    report = replay(population(), SPLIT)
    accounts = [
        vintage("户一", "甲渠道"),
        vintage("户二", "乙渠道"),
        vintage("户三", "甲渠道"),
    ]
    scores = [
        score("户一", probability=0.8),
        score("户二", probability=None, state="训练分布外"),
        score("户三", probability=0.3),
    ]
    applied = service.apply_replay(scores, accounts, report)
    payload = service.evidence(report, applied)
    assert payload["采用校准"] == CalibrationMode.CHANNEL.value
    assert payload["同一批复核户月"] == 6
    assert payload["Brier门槛"] is True and payload["漏判门槛"] is True
    counts = payload["概率来源计数"]
    assert sum(counts.values()) == 3
    assert counts[ProbabilitySource.CHANNEL.value] == 2
    assert counts[ProbabilitySource.UNSUPPORTED.value] == 1
    assert {row["渠道"] for row in payload["records"]} == set(CHANNELS)
    diagnostics = report_diagnostics(payload)
    assert diagnostics["有效"] == len(payload["records"])
    assert diagnostics["分组"] == "渠道"


def test_sample_book_replay_picks_channel_calibration():
    # 端到端：样例数据上双门槛同时满足，当期 18 户可评分、1 户分布外不补估。
    from invoicecover.pipeline import run

    result = run(6)
    replay_payload = result["stages"][3]["校准回放"]
    assert replay_payload["采用校准"] == "渠道校准"
    assert replay_payload["门槛同时满足"] is True
    assert replay_payload["渠道Brier"] < replay_payload["全体Brier"]
    assert replay_payload["渠道线下漏判"] <= replay_payload["全体线下漏判"]
    assert replay_payload["概率来源计数"]["分布外不补估"] == 1
    sources = {row["debtor"]: row["calibration"] for row in result["rows"]}
    unsupported = [
        row for row in result["rows"] if row["risk"] is None
    ]
    assert unsupported and all(
        sources[row["debtor"]] == ProbabilitySource.UNSUPPORTED.value
        for row in unsupported
    )
    assert result["metrics"]["校准方式"] == "渠道校准"
