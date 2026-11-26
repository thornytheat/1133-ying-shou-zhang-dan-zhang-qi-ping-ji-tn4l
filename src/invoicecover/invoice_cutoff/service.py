from csv import DictReader
from pathlib import Path
from .contracts import BillingBook, DocumentFlag
from .engine import build_book, summarize_channels


def from_csv(path: Path, *, cutoff):
    with path.open(newline="", encoding="utf-8-sig") as source:
        rows = DictReader(source)
        required = {
            "invoice",
            "debtor",
            "channel",
            "issued",
            "due",
            "posted",
            "revision",
            "status",
            "amount_cny",
        }
        if not required <= set(rows.fieldnames or ()):
            raise ValueError("账单字段缺失")
        return build_book(rows, cutoff)


def evidence(book: BillingBook):
    holds = sum(record.flag != DocumentFlag.ACCEPTED for record in book.decisions)
    detail = [
        {
            "账单": record.number,
            "结果": record.flag,
            "版本": record.revision,
            "金额（分）": record.cents,
            "输入笔数": record.records,
        }
        for record in book.decisions
    ]
    channels = [
        {"渠道": channel, "户数": count, "账款（分）": amount}
        for channel, count, amount in summarize_channels(book.bills)
    ]
    return {
        "title": "账单归户",
        "summary": f"有效 {len(book.bills)} 笔，需核查 {holds} 笔",
        "records": detail,
        "channels": channels,
    }


def balances_by_debtor(book):
    balances = {}
    for bill in book.bills:
        balances[bill.debtor] = balances.get(bill.debtor, 0) + bill.cents
    return dict(sorted(balances.items()))
