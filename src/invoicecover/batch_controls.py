from .invoice_cutoff import diagnostics as invoice_cutoff
from .repayment_clock import diagnostics as repayment_clock
from .aging_features import diagnostics as aging_features
from .term_scorecard import diagnostics as term_scorecard
from .credit_terms import diagnostics as credit_terms
from .collection_vintage import diagnostics as collection_vintage

PROJECTIONS = (
    invoice_cutoff,
    repayment_clock,
    aging_features,
    term_scorecard,
    credit_terms,
    collection_vintage,
)
TITLES = (
    "合同敞口",
    "逾期回收",
    "账龄集中度",
    "保序分箱支持度",
    "排位缺口",
    "漂移贡献",
)


def annotate(stages):
    if len(stages) != len(PROJECTIONS):
        raise ValueError("业务诊断与运行阶段数量不一致")
    enriched = []
    for stage, implementation, title in zip(stages, PROJECTIONS, TITLES, strict=True):
        diagnostics = implementation.report(stage)
        enriched.append({**stage, "诊断": {**diagnostics, "标题": title}})
    return enriched
