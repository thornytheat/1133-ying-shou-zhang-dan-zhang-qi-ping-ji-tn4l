from csv import DictReader
from .contracts import CashBook
from .engine import reconcile, settled_late


def from_csv(path, book):
    with path.open(newline="", encoding="utf-8-sig") as source:
        return reconcile(book.bills, DictReader(source), book.cutoff)


def evidence(ledger: CashBook):
    rows = []
    for state in ledger.statements:
        rows.append(
            {
                "账单": state.invoice,
                "已结（分）": state.paid,
                "未结（分）": state.outstanding,
                "结清日期": state.paid_on.isoformat() if state.paid_on else None,
                "溢缴（分）": sum(item.suspense for item in state.entries),
            }
        )
    quarantine = [
        {
            "回单": row.receipt,
            "账单": row.invoice,
            "状态": row.flag,
            "暂挂（分）": row.suspense,
        }
        for row in ledger.custody
    ]
    return {
        "title": "回款时点",
        "summary": f"回款 {ledger.received / 100:,.2f} 元，暂挂或迟到 {len(quarantine)} 笔",
        "records": rows,
        "quarantine": quarantine,
    }


def labels(bills, ledger, outcome_date):
    due = {bill.number: bill.due for bill in bills}
    return {
        row.invoice: settled_late(row, due[row.invoice], outcome_date)
        for row in ledger.statements
    }
