from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class CashDisposition(StrEnum):
    POSTED = "已入账"
    LATE_POST = "待入账"
    UNKNOWN_INVOICE = "缺账单"
    AMBIGUOUS = "回款编号冲突"
    OVERPAID = "超额回款"
    INVALID = "回款字段错误"


@dataclass(frozen=True, order=True)
class CashTransfer:
    receipt: str
    invoice: str
    happened: date
    recorded: date
    cents: int

    def __post_init__(self):
        if not self.receipt or not self.invoice or self.cents <= 0:
            raise ValueError("缺回款编号、账单或正额")
        if self.recorded < self.happened:
            raise ValueError("入账日早于到账日")


@dataclass(frozen=True)
class CashEntry:
    receipt: str
    invoice: str
    applied: int
    suspense: int
    flag: CashDisposition
    happened: date | None


@dataclass(frozen=True)
class Settlement:
    invoice: str
    outstanding: int
    paid: int
    paid_on: date | None
    entries: tuple[CashEntry, ...]

    def __post_init__(self):
        if min(self.outstanding, self.paid) < 0:
            raise ValueError("回款与余额不能为负")
        if sum(entry.applied for entry in self.entries) != self.paid:
            raise ValueError("回单分配与已回款金额不等")


@dataclass(frozen=True)
class CashBook:
    statements: tuple[Settlement, ...]
    custody: tuple[CashEntry, ...]

    @property
    def received(self):
        return sum(item.paid for item in self.statements)
