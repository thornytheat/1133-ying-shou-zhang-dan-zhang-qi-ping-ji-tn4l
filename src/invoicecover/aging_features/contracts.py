from dataclasses import dataclass
from datetime import date
from math import isfinite

FEATURES = (
    "未结比例",
    "逾期比例",
    "最久逾期天数",
    "最早开票天数",
    "账单笔数",
    "金额对数",
)


@dataclass(frozen=True)
class Vintage:
    debtor: str
    channel: str
    as_of: date
    amounts: tuple[int, int, int, int]
    values: tuple[float, ...]
    due_soon: int
    target: int | None = None

    def __post_init__(self):
        if len(self.values) != len(FEATURES) or not all(
            isfinite(value) for value in self.values
        ):
            raise ValueError("账龄特征维度或数值无效")
        if len(self.amounts) != 4 or min(self.amounts) < 0 or self.due_soon < 0:
            raise ValueError("账龄桶金额不合法")
        if self.target not in (None, 0, 1):
            raise ValueError("标签须为已结论的二分类值")


@dataclass(frozen=True)
class FeatureScaler:
    center: tuple[float, ...]
    scales: tuple[float, ...]
    minimum: tuple[float, ...]
    maximum: tuple[float, ...]

    def __post_init__(self):
        lengths = {
            len(self.center),
            len(self.scales),
            len(self.minimum),
            len(self.maximum),
        }
        if lengths != {len(FEATURES)} or min(self.scales) <= 0:
            raise ValueError("训练尺度维度或方差无效")
