from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class DocumentFlag(StrEnum):
    ACCEPTED = "已登记"
    FUTURE = "截点后入账"
    VOID = "已冲销"
    CONFLICT = "同版金额冲突"
    INVALID = "账单字段无效"


@dataclass(frozen=True, order=True)
class Bill:
    number: str
    debtor: str
    channel: str
    issued: date
    due: date
    posted: date
    revision: int
    cents: int
    void: bool = False

    def __post_init__(self):
        if not self.number or not self.debtor or not self.channel:
            raise ValueError("缺少账单、欠款方或渠道")
        if self.revision < 1 or self.due < self.issued or self.posted < self.issued:
            raise ValueError("账单版本或时序无效")
        if self.cents <= 0:
            raise ValueError("账面金额必须为正")


@dataclass(frozen=True)
class EntryDecision:
    number: str
    flag: DocumentFlag
    revision: int
    cents: int
    records: int = 1


@dataclass(frozen=True)
class BillingBook:
    cutoff: date
    bills: tuple[Bill, ...]
    decisions: tuple[EntryDecision, ...]
    malformed: int

    @property
    def total_cents(self):
        return sum(bill.cents for bill in self.bills)
