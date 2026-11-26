from datetime import date
from invoicecover.invoice_cutoff.contracts import Bill
from invoicecover.repayment_clock.contracts import CashDisposition
from invoicecover.repayment_clock.engine import reconcile, settled_late
from invoicecover.repayment_clock.service import evidence

CUTOFF = date(2026, 8, 28)


def bill():
    return Bill(
        "INV-19",
        "比安",
        "园区",
        date(2026, 8, 1),
        date(2026, 8, 22),
        date(2026, 8, 2),
        1,
        4000,
    )


def cash(**overrides):
    return {
        "receipt": "COL-05",
        "invoice": "INV-19",
        "happened": "2026-08-20",
        "recorded": "2026-08-20",
        "amount_cny": "21.04",
        **overrides,
    }


def test_late_entry_is_kept_in_suspense_not_backdated():
    book = reconcile([bill()], [cash(recorded="2026-08-29")], CUTOFF)
    assert book.statements[0].outstanding == 4000
    assert book.custody[0].flag == CashDisposition.LATE_POST
    assert book.custody[0].suspense == 2104


def test_overpayment_is_conserved_at_cent_precision():
    # TRAP-10
    book = reconcile(
        [bill()], [cash(), cash(receipt="COL-06", amount_cny="22.08")], CUTOFF
    )
    state = book.statements[0]
    assert state.paid == 4000
    assert state.outstanding == 0
    assert sum(row.applied + row.suspense for row in state.entries) == 4312
    assert state.entries[1].flag == CashDisposition.OVERPAID


def test_duplicate_receipt_does_not_double_the_deposit():
    book = reconcile([bill()], [cash(), cash()], CUTOFF)
    assert book.received == 2104
    assert len(book.statements[0].entries) == 1


def test_conflicting_receipts_are_isolated():
    book = reconcile([bill()], [cash(), cash(amount_cny="1.00")], CUTOFF)
    assert book.received == 0
    assert book.custody[0].flag == CashDisposition.AMBIGUOUS


def test_reference_without_bill_is_reported():
    book = reconcile([bill()], [cash(invoice="INV-20")], CUTOFF)
    assert book.custody[0].flag == CashDisposition.UNKNOWN_INVOICE
    assert evidence(book)["quarantine"][0]["账单"] == "INV-20"


def test_settlement_date_on_due_is_on_time():
    book = reconcile(
        [bill()],
        [cash(happened="2026-08-22", recorded="2026-08-22", amount_cny="40.00")],
        CUTOFF,
    )
    assert settled_late(book.statements[0], bill().due, CUTOFF) == 0


def test_unmatured_unpaid_label_is_censored():
    state = reconcile([bill()], [], CUTOFF).statements[0]
    assert settled_late(state, bill().due, bill().due) is None
    assert settled_late(state, bill().due, CUTOFF) == 1


def test_invalid_posting_order_is_not_a_payment():
    book = reconcile([bill()], [cash(recorded="2026-08-19")], CUTOFF)
    assert book.received == 0
    assert book.custody[0].flag == CashDisposition.INVALID
