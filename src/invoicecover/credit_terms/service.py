from .contracts import QueueSheet, ReviewPolicy, Term
from .engine import dispatch, expected_exposure


def rows(sheet: QueueSheet):
    return [
        {
            "debtor": item.debtor,
            "balance": item.exposure / 100,
            "overdue": item.overdue / 100,
            "risk": round(item.risk, 5) if item.risk is not None else None,
            "decision": item.term,
            "seat": item.seat,
            "reason": item.reason,
        }
        for item in sheet.decisions
    ]


def evidence(sheet):
    visible = rows(sheet)
    records = [
        {
            "经销商": row["debtor"],
            "决定": row["decision"],
            "排位": row["seat"],
            "依据": row["reason"],
        }
        for row in visible
    ]
    waiting = sum(row.term == Term.WAIT for row in sheet.decisions)
    expected, excluded = expected_exposure(sheet.decisions)
    return {
        "title": "账期裁定",
        "summary": f"待审 {waiting} 户，剩余 {sheet.open_seats} 个复核席位",
        "records": records,
        "expected_exposure_yuan": float(expected),
        "out_of_support_cents": excluded,
    }
