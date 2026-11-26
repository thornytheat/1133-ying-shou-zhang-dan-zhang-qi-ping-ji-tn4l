from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from .contracts import Bill, BillingBook, DocumentFlag, EntryDecision


def money_to_cents(raw):
    try:
        amount = Decimal(raw)
        cents = amount * 100
        if not cents.is_finite() or cents != cents.to_integral_value():
            raise ValueError("金额不是有限的两位小数")
        return int(cents)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("金额无法解析") from exc


def read_bill(row):
    status = row["status"]
    if status not in ("open", "void"):
        raise ValueError("状态未知")
    return Bill(
        row["invoice"].strip(),
        row["debtor"].strip(),
        row["channel"].strip(),
        date.fromisoformat(row["issued"]),
        date.fromisoformat(row["due"]),
        date.fromisoformat(row["posted"]),
        int(row["revision"]),
        money_to_cents(row["amount_cny"]),
        status == "void",
    )


def adjudicate_revisions(records, cutoff):
    eligible = defaultdict(list)
    decisions = []
    for row in records:
        if row.posted > cutoff:
            decisions.append(
                EntryDecision(row.number, DocumentFlag.FUTURE, row.revision, row.cents)
            )
        else:
            eligible[row.number].append(row)
    approved = []
    for number, group in sorted(eligible.items()):
        newest = max(item.revision for item in group)
        candidates = {item for item in group if item.revision == newest}
        if len(candidates) > 1:
            decisions.append(
                EntryDecision(number, DocumentFlag.CONFLICT, newest, 0, len(group))
            )
            continue
        row = next(iter(candidates))
        if row.void:
            flag = DocumentFlag.VOID
        elif len({(item.debtor, item.channel) for item in group}) > 1:
            flag = DocumentFlag.CONFLICT
        else:
            flag = DocumentFlag.ACCEPTED
            approved.append(row)
        decisions.append(
            EntryDecision(row.number, flag, row.revision, row.cents, len(group))
        )
    return tuple(approved), tuple(
        sorted(
            decisions, key=lambda row: (row.number, row.revision, row.flag, row.cents)
        )
    )


def build_book(rows, as_of):
    clean = []
    errors = []
    for row in rows:
        try:
            clean.append(read_bill(row))
        except (ValueError, KeyError, TypeError, AttributeError):
            number = str(row.get("invoice") or "?") if isinstance(row, dict) else "?"
            errors.append(EntryDecision(number, DocumentFlag.INVALID, 0, 0))
    accepted, decisions = adjudicate_revisions(clean, as_of)
    return BillingBook(
        as_of,
        accepted,
        decisions + tuple(sorted(errors, key=lambda row: row.number)),
        len(errors),
    )


def summarize_channels(bills):
    totals = defaultdict(int)
    accounts = defaultdict(set)
    for bill in bills:
        totals[bill.channel] += bill.cents
        accounts[bill.channel].add(bill.debtor)
    return [
        (channel, len(accounts[channel]), amount)
        for channel, amount in sorted(totals.items())
    ]
