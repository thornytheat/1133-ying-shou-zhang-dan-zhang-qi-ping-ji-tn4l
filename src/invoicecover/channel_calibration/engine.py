from collections import defaultdict
from math import fsum

from ..aging_features.service import fit_scaler, scaled_features
from ..term_scorecard.engine import calibrate, dot, isotonic, logistic, logistic_fit
from .contracts import (
    CalibrationComparison,
    CalibrationMode,
    ChannelHoldout,
    ReplayReport,
)


def _raw_scores(training, holdout, penalty):
    """原始打分模型只用留出期开始前已成熟的户月，避免未来信息混入。"""
    scaler = fit_scaler(training)
    weights, intercept = logistic_fit(
        [scaled_features(item, scaler) for item in training],
        [item.target for item in training],
        penalty,
    )
    predictions = tuple(
        (
            logistic(intercept + dot(weights, scaled_features(item, scaler))),
            item.target,
            item.channel,
        )
        for item in holdout
    )
    return scaler, weights, intercept, predictions


def _brier(pairs):
    if not pairs:
        return None
    return fsum((probability - target) ** 2 for probability, target in pairs) / len(
        pairs
    )


def _missed_events(pairs, high_risk_line):
    """高风险线之下的逾期户月：渠道校准不得让这类漏判增加。"""
    if not pairs:
        return None
    return sum(
        1 for probability, target in pairs if target == 1 and probability < high_risk_line
    )


def replay(population, split, penalty=0.08, high_risk_line=0.72):
    training = tuple(
        item for item in population if item.as_of < split and item.target is not None
    )
    # 回放拟合只接受留出期开始前已成熟的逾期结论；尚未成熟的标签直接排除。
    holdout = tuple(
        item for item in population if item.as_of >= split and item.target is not None
    )
    if not training or not holdout:
        raise ValueError("回放需要训练与留出两段已成熟户月")
    _, _, _, predictions = _raw_scores(training, holdout, penalty)
    pooled_bands = isotonic([(score, target) for score, target, _ in predictions])

    grouped = defaultdict(list)
    for score, target, channel in predictions:
        grouped[channel].append((score, target))

    channel_evidence = []
    channel_bands = {}
    for channel in sorted(grouped):
        points = grouped[channel]
        events = sum(target for _, target in points)
        # 留出期可评分户月须有逾期也有正常，才有资格分渠道保序校准。
        eligible = 0 < events < len(points)
        bands = isotonic(points) if eligible else ()
        if eligible:
            channel_bands[channel] = bands
        channel_evidence.append(
            ChannelHoldout(channel, len(points), events, eligible, tuple(bands))
        )

    # 用同一批户月比较：全体校准在全体上的口径不变，渠道侧只纳入合格渠道。
    common = tuple(item for item in predictions if item[2] in channel_bands)
    pooled_pairs = tuple(
        (calibrate(pooled_bands, score), target) for score, target, _ in common
    )
    channel_pairs = tuple(
        (calibrate(channel_bands[channel], score), target)
        for score, target, channel in common
    )
    pooled_brier = _brier(pooled_pairs)
    channel_brier = _brier(channel_pairs)
    pooled_misses = _missed_events(pooled_pairs, high_risk_line)
    channel_misses = _missed_events(channel_pairs, high_risk_line)
    brier_improved = (
        pooled_brier is not None
        and channel_brier is not None
        and channel_brier < pooled_brier
    )
    misses_not_increased = (
        pooled_misses is not None
        and channel_misses is not None
        and channel_misses <= pooled_misses
    )
    comparison = CalibrationComparison(
        len(common),
        pooled_brier,
        channel_brier,
        pooled_misses,
        channel_misses,
        high_risk_line,
        brier_improved,
        misses_not_increased,
    )

    eligible_names = tuple(row.channel for row in channel_evidence if row.eligible)
    reasons = []
    if not eligible_names:
        reasons.append("留出期各渠道均缺少逾期或正常户月，不具备分渠道校准条件")
    else:
        reasons.append(
            f"合格渠道 {len(eligible_names)} 个，同一批 {len(common)} 个户月上比较"
        )
        reasons.append(
            f"概率平方误差：全体 {pooled_brier:.6f}，渠道 {channel_brier:.6f}，"
            + ("渠道更小" if brier_improved else "渠道未更小")
        )
        reasons.append(
            f"高风险线 {high_risk_line:.2f} 下漏判逾期户月："
            f"全体 {pooled_misses}，渠道 {channel_misses}，"
            + ("未增加" if misses_not_increased else "出现增加")
        )
    mode = CalibrationMode.CHANNEL if comparison.gate_passed else CalibrationMode.POOLED
    if mode is CalibrationMode.POOLED and eligible_names:
        reasons.append("门槛未同时满足，沿用全体校准")
    if mode is CalibrationMode.CHANNEL:
        reasons.append("两项门槛同时满足，采用渠道校准")
    return ReplayReport(
        split,
        len(training),
        len(holdout),
        mode,
        eligible_names,
        tuple(channel_evidence),
        comparison,
        tuple(reasons),
        tuple(pooled_bands),
        dict(channel_bands),
    )


def calibrated_probability(score_row, channel, report):
    """按回放结论给出当期概率；分布外户返回 None，不补估。"""
    if score_row.probability is None:
        return None
    if report.mode is CalibrationMode.CHANNEL and channel in report.channel_bands:
        return calibrate(report.channel_bands[channel], score_row.percentile)
    return calibrate(report.pooled_bands, score_row.percentile)
