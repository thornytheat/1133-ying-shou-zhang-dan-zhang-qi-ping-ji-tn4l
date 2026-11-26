from datetime import date
import pytest
from invoicecover.invoice_cutoff.contracts import DocumentFlag
from invoicecover.invoice_cutoff.engine import build_book, money_to_cents
from invoicecover.invoice_cutoff.service import balances_by_debtor, evidence

AS_OF = date(2026, 9, 1)


def invoice(**changes):
    return {
        "invoice": "00014",
        "debtor": "华北云桥",
        "channel": "经销",
        "issued": "2026-08-01",
        "due": "2026-09-04",
        "posted": "2026-08-02",
        "revision": "1",
        "status": "open",
        "amount_cny": "340.13",
        **changes,
    }


def test_conflicting_revisions_are_not_last_write_wins():
    # TRAP-14
    first = invoice()
    alternate = invoice(amount_cny="350.13")
    left = build_book([first, alternate], AS_OF)
    right = build_book([alternate, first], AS_OF)
    assert left == right
    assert left.bills == ()
    assert left.decisions[0].flag == DocumentFlag.CONFLICT


def test_future_version_does_not_change_book():
    # TRAP-42
    visible = invoice()
    future = invoice(revision="2", amount_cny="900.00", posted="2026-09-02")
    augmented = build_book([future, visible], AS_OF)
    assert build_book([visible], AS_OF).bills == augmented.bills
    assert augmented.decisions[-1].flag == DocumentFlag.FUTURE


def test_void_wins_over_previous_revision():
    result = build_book([invoice(), invoice(revision="2", status="void")], AS_OF)
    assert result.total_cents == 0
    assert result.decisions[0].flag == DocumentFlag.VOID


def test_decimal_units_preserve_a_large_integer():
    assert money_to_cents("90071992547409.93") == 9007199254740993
    with pytest.raises(ValueError):
        money_to_cents("2.017")
    with pytest.raises(ValueError):
        money_to_cents("NaN")


def test_duplicate_copies_preserve_amount_and_count():
    result = build_book([invoice(), invoice()], AS_OF)
    assert result.total_cents == 34013
    assert result.decisions[0].records == 2
    assert result.bills[0].number == "00014"


def test_wrong_timing_and_blank_channel_are_quarantined():
    result = build_book([invoice(channel=""), invoice(due="2026-07-31")], AS_OF)
    assert result.malformed == 2
    assert evidence(result)["records"][0]["结果"] == DocumentFlag.INVALID


def test_book_channel_total_and_debtor_balance_agree():
    result = build_book(
        [invoice(), invoice(invoice="00015", amount_cny="1.05", channel="直营")], AS_OF
    )
    detail = evidence(result)
    assert sum(item["账款（分）"] for item in detail["channels"]) == 34118
    assert balances_by_debtor(result) == {"华北云桥": 34118}


def test_new_revision_cannot_silently_move_debt_to_another_customer():
    result = build_book([invoice(), invoice(revision="2", debtor="华北益泉")], AS_OF)
    assert result.decisions[0].flag == DocumentFlag.CONFLICT
    assert result.bills == ()
