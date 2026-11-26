# 应收账单账期评级

面向账期管理的本地工作台。内置业务样例覆盖经销商账单逾期建模、分箱校准与账期复核。样例采用确定性构造，适合复现实验和核查边界行为。

## 启动

```sh
docker compose up --build -d
```

打开 `http://127.0.0.1:18212/` 查看账期复核单。左侧六个入口可展开运行证据。调整「账期复核名额（户）」，点击「重算账期」比较处置结果。结束后执行 `docker compose down --remove-orphans`。

## 独立业务模块

- 账单归户 `invoice_cutoff`
- 回款时点 `repayment_clock`
- 账龄特征 `aging_features`
- 账期建模 `term_scorecard`
- 账期裁定 `credit_terms`
- 回款复盘 `collection_vintage`

## 查看运行结果

- `GET /api/overview` 返回默认运行及其指纹。
- `POST /api/scenario` 接收 `{"capacity": 3}`。入口接受 1–100 的整数，应用样例时使用该业务额度。
- `GET /api/stages/collection_vintage` 查看该环节的独立证据，支持 `?capacity=3`。

```sh
docker compose exec -T app python -m invoicecover.delivery evaluate --capacity 3
docker compose exec -T app pytest -q
```

数据和模型约定见 [业务契约](docs/SPEC.md)。模块、例外规则与验证入口见 [业务深度](docs/DEPTH.md)。
