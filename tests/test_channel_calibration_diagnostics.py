from math import inf, nan

from invoicecover.channel_calibration.diagnostics import (
    GROUP,
    MEASURE,
    MODE,
    REFERENCE,
    THRESHOLD,
    report,
    summarize,
)


def observations(values, group="甲渠道"):
    return [
        {REFERENCE: f"凭证-{index}", GROUP: group, MEASURE: value}
        for index, value in enumerate(values)
    ]


def test_channel_replay_empty_stage_has_explicit_total():
    result = report({"records": []})
    assert result["有效"] == 0
    assert result["未知"] == 0
    assert result["明细"] == []


def test_channel_replay_non_finite_values_are_unknown():
    result = report({"records": observations([None, inf, nan, True, "12"])})
    assert result["有效"] == 0
    assert result["未知"] == 5
    assert result["明细"][0]["median"] is None


def test_channel_replay_flags_channels_below_support_threshold():
    below = THRESHOLD - 1
    cohort = summarize(observations([below, THRESHOLD, THRESHOLD + 4]))[0]
    assert cohort.median == THRESHOLD
    assert cohort.at_risk == 1
    expected = "甲渠道" if GROUP == REFERENCE else "凭证-0"
    assert cohort.critical_references == (expected,)
    assert MODE == "low"


def test_channel_replay_permutation_preserves_counts_and_order():
    source = observations([6, 18], "甲渠道") + observations([4, None, 12], "乙渠道")
    initial = summarize(source)
    assert len(initial) == 2
    assert sum(row.observations for row in initial) == 4
    assert summarize(list(reversed(source))) == initial


def test_channel_replay_missing_group_keeps_original_evidence():
    row = {MEASURE: 9, REFERENCE: "已知渠道"}
    row.pop(GROUP, None)
    result = summarize([row])[0]
    assert result.cohort == "未分组"
    assert result.total == 9
