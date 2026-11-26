from invoicecover.pipeline import run


def test_full_cycle_has_balanced_cash_and_auditable_holdbacks():
    result = run()
    assert len(result["stages"]) == 6
    assert result["stages"][-1]["cash"]["cents_gap"] == 0
    assert result["stages"][1]["quarantine"]
    assert result["metrics"]["未达评分支持"] >= 1
    assert len(result["series"]) >= 5


def test_capacity_changes_queue_but_preserves_posting_and_score():
    a = run(1)
    b = run(4)
    assert a["stages"][:4] == b["stages"][:4]
    assert a["metrics"]["进入复核"] <= 1
    assert b["metrics"]["进入复核"] >= 1
