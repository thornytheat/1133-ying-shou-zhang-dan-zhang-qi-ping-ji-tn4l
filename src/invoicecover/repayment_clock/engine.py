from collections import defaultdict
from datetime import date
from .contracts import CashBook, CashDisposition, CashEntry, CashTransfer, Settlement
from decimal import Decimal, InvalidOperation


def money_to_cents(raw):
    try:
        value = Decimal(raw) * 100
        if not value.is_finite() or value != value.to_integral_value():
            raise ValueError("金额无效")
        return int(value)
    except (InvalidOperation, TypeError) as error:
        raise ValueError("金额无效") from error


def transfer_row(row):
    return CashTransfer(
        row["receipt"].strip(),
        row["invoice"].strip(),
        date.fromisoformat(row["happened"]),
        date.fromisoformat(row["recorded"]),
        money_to_cents(row["amount_cny"]),
    )


def visible_transfers(rows, as_of):
    withheld = []
    candidates = defaultdict(set)
    for raw in rows:
        try:
            row = transfer_row(raw)
        except (AttributeError, TypeError, ValueError, KeyError):
            withheld.append(
                CashEntry(
                    str(raw.get("receipt", "?")),
                    "",
                    0,
                    0,
                    CashDisposition.INVALID,
                    None,
                )
            )
            continue
        if row.recorded > as_of or row.happened > as_of:
            withheld.append(
                CashEntry(
                    row.receipt,
                    row.invoice,
                    0,
                    row.cents,
                    CashDisposition.LATE_POST,
                    row.happened,
                )
            )
            continue
        candidates[row.receipt].add(row)
    usable = []
    for receipt, entries in sorted(candidates.items()):
        if len(entries) != 1:
            withheld.append(
                CashEntry(receipt, "", 0, 0, CashDisposition.AMBIGUOUS, None)
            )
        else:
            usable.append(next(iter(entries)))
    return usable, withheld


def reconcile(bills, rows, as_of):
    book = {bill.number: bill for bill in bills}
    if len(book) != len(bills):
        raise ValueError("重复账单")
    transfers, held = visible_transfers(rows, as_of)
    by_invoice = defaultdict(list)
    for transfer in transfers:
        if transfer.invoice not in book:
            held.append(
                CashEntry(
                    transfer.receipt,
                    transfer.invoice,
                    0,
                    transfer.cents,
                    CashDisposition.UNKNOWN_INVOICE,
                    transfer.happened,
                )
            )
        else:
            by_invoice[transfer.invoice].append(transfer)
    statements = []
    for invoice, document in sorted(book.items()):
        balance = document.cents
        entries = []
        paid_on = None
        ordered = sorted(
            by_invoice[invoice], key=lambda item: (item.happened, item.receipt)
        )
        for transfer in ordered:
            applied = min(balance, transfer.cents)
            balance -= applied
            remainder = transfer.cents - applied
            category = CashDisposition.OVERPAID if remainder else CashDisposition.POSTED
            entries.append(
                CashEntry(
                    transfer.receipt,
                    invoice,
                    applied,
                    remainder,
                    category,
                    transfer.happened,
                )
            )
            if balance == 0 and paid_on is None:
                paid_on = transfer.happened
        statements.append(
            Settlement(
                invoice, balance, document.cents - balance, paid_on, tuple(entries)
            )
        )
    return CashBook(
        tuple(statements),
        tuple(sorted(held, key=lambda item: (item.receipt, item.flag, item.suspense))),
    )


def settled_late(statement, due, observed):
    if statement.paid_on is not None:
        return int(statement.paid_on > due)
    if observed > due:
        return 1
    return None
