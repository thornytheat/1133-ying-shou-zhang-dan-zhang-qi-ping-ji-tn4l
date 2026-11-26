# 应收账单账期评级的业务深度

AI/ML / 传统ML

## 功能模块

| 模块 | 职责 | 使用的计算或裁决 | 核心文件 | 独立测试 |
|---|---|---|---|---|
| M1 账单归户 | 账单归户 | 双时间可见性与发票版本冲突隔离 | `src/invoicecover/invoice_cutoff/contracts.py` `src/invoicecover/invoice_cutoff/engine.py` `src/invoicecover/invoice_cutoff/service.py` | `tests/test_invoice_cutoff.py` |
| M2 回款时点 | 回款时点 | 按实际到账次序逐分抵扣溢缴暂挂 | `src/invoicecover/repayment_clock/contracts.py` `src/invoicecover/repayment_clock/engine.py` `src/invoicecover/repayment_clock/service.py` | `tests/test_repayment_clock.py` |
| M3 账龄特征 | 账龄特征 | 账龄分桶与折内中心化 | `src/invoicecover/aging_features/contracts.py` `src/invoicecover/aging_features/engine.py` `src/invoicecover/aging_features/service.py` | `tests/test_aging_features.py` |
| M4 账期建模 | 账期建模 | 时序逻辑回归、保序校准和分布外拦截 | `src/invoicecover/term_scorecard/contracts.py` `src/invoicecover/term_scorecard/engine.py` `src/invoicecover/term_scorecard/service.py` | `tests/test_term_scorecard.py` |
| M5 账期裁定 | 账期裁定 | 按复核优先级排序，逐席守恒 | `src/invoicecover/credit_terms/contracts.py` `src/invoicecover/credit_terms/engine.py` `src/invoicecover/credit_terms/service.py` | `tests/test_credit_terms.py` |
| M6 回款复盘 | 回款复盘 | 校准分布 PSI 与逐账单金额复核 | `src/invoicecover/collection_vintage/contracts.py` `src/invoicecover/collection_vintage/engine.py` `src/invoicecover/collection_vintage/service.py` | `tests/test_collection_vintage.py` |

## 边界与证据

| 编号 | 触发条件 | 风险 | 处理规则 | 位置 | 验证 |
|---|---|---|---|---|---|
| TRAP-14 | 同版本账单冲突 | 产生错误的业务记录或评分 | 隔离并保证结果与输入顺序无关 | `src/invoicecover/invoice_cutoff/engine.py` | `tests/test_invoice_cutoff.py::test_conflicting_revisions_are_not_last_write_wins` |
| TRAP-10 | 多笔小数回款超过账面 | 产生错误的业务记录或评分 | 逐分对账并暂挂余额 | `src/invoicecover/repayment_clock/engine.py` | `tests/test_repayment_clock.py::test_overpayment_is_conserved_at_cent_precision` |
| TRAP-23 | 到期日和分箱边缘 | 产生错误的业务记录或评分 | 每笔只计入一个区间 | `src/invoicecover/aging_features/engine.py` | `tests/test_aging_features.py::test_aging_boundaries_are_exclusive` |
| TRAP-32 | 特征含大偏移或常数 | 产生错误的业务记录或评分 | 中心化求方差并兜底 | `src/invoicecover/aging_features/engine.py` | `tests/test_aging_features.py::test_centered_variance_survives_large_offset_and_constants` |
| TRAP-53 | 同户与高额样本同时评分 | 产生错误的业务记录或评分 | 推理冻结训练尺度 | `src/invoicecover/aging_features/engine.py` | `tests/test_aging_features.py::test_frozen_scale_ignores_batch_peers` |
| TRAP-31 | 极端线性得分 | 产生错误的业务记录或评分 | 分支计算 Sigmoid | `src/invoicecover/term_scorecard/engine.py` | `tests/test_term_scorecard.py::test_logistic_extremes_are_finite` |
| TRAP-43 | 留出集无正类 | 产生错误的业务记录或评分 | 报告 AP 未定义和 ECE | `src/invoicecover/term_scorecard/engine.py` | `tests/test_term_scorecard.py::test_degenerate_holdout_reports_undefined_average_precision` |
| TRAP-44 | 相邻校准组违序 | 产生错误的业务记录或评分 | PAV 合并并计算 ECE | `src/invoicecover/term_scorecard/engine.py` | `tests/test_term_scorecard.py::test_isotonic_repairs_reversed_probability_order` |
| TRAP-42 | 追加未来观测 | 产生错误的业务记录或评分 | 历史模型权重不变 | `src/invoicecover/term_scorecard/engine.py` | `tests/test_term_scorecard.py::test_calibration_data_never_changes_training_weights` |
| TRAP-19 | 超期及高分同时触发 | 产生错误的业务记录或评分 | 先敞口再高分，次序确定 | `src/invoicecover/credit_terms/engine.py` | `tests/test_credit_terms.py::test_competing_rules_keep_conservative_priority_independent_of_input_order` |
