from datetime import date, timedelta
from .credit_terms.seat_replay import review_pressure
from .repayment_clock.vintage_matching import recovery_records, recovery_snapshot
from .term_scorecard.score_evaluation import evaluate_folds, reliability_notes
from pathlib import Path
from .aging_features import service as aging
from .collection_vintage import service as collection
from .credit_terms import service as review
from .invoice_cutoff import service as invoice
from .repayment_clock import service as payments
from .term_scorecard import service as model

DATA = Path(__file__).resolve().parents[2] / "sample_data"
AS_OF = date(2026, 9, 1)
SPLIT = date(2026, 6, 1)


def run(capacity=None):
    seats = 6 if capacity is None else capacity
    invoices = invoice.from_csv(DATA / "september_open_invoices.csv", cutoff=AS_OF)
    cash = payments.from_csv(DATA / "clearing_house_receipts.csv", invoices)
    accounts = aging.aggregate(invoices.bills, cash.statements, AS_OF)
    history = aging.training_periods(DATA / "matured_month_end_snapshots.csv", AS_OF)
    risk_model = model.fit(history, SPLIT)
    scores = model.evaluate_book(risk_model, accounts)
    queue = review.dispatch(accounts, scores, review.ReviewPolicy(seats))
    distribution = collection.drift(
        collection.historical_probabilities(risk_model.card),
        [row.probability for row in scores],
    )
    integrity = collection.cash_integrity(invoices.bills, cash)
    operations = review.rows(queue)
    horizon = 20
    historical_invoices = invoice.from_csv(
        DATA / "september_open_invoices.csv", cutoff=AS_OF - timedelta(days=horizon)
    )
    opening = payments.from_csv(
        DATA / "clearing_house_receipts.csv", historical_invoices
    )
    recoveries = recovery_snapshot(
        invoices.bills, opening.statements, cash.statements, AS_OF, horizon
    )
    holdout = reliability_notes(
        evaluate_folds(history, [(date(2026, 4, 1), SPLIT, AS_OF)])
    )
    forecast_evidence = {**model.evidence(risk_model), "独立留出": holdout}
    credit_evidence = {
        **review.evidence(queue),
        "额度复盘": review_pressure(accounts, scores, queue.policy),
    }
    cash_evidence = {
        **payments.evidence(cash),
        "催收复盘": recovery_records(recoveries),
    }
    return {
        "metrics": {
            "复核席位": seats,
            "进入复核": seats - queue.open_seats,
            "未结余额（元）": integrity.cents_open / 100,
            "未达评分支持": distribution.excluded,
        },
        "columns": {
            "debtor": "经销商",
            "balance": "未结（元）",
            "overdue": "逾期（元）",
            "risk": "逾期概率",
            "decision": "账期处置",
            "seat": "复核排位",
            "reason": "依据",
        },
        "rows": operations,
        "series": [
            {"label": row.debtor, "value": round(row.probability, 5)}
            for row in scores
            if row.probability is not None
        ],
        "stages": [
            invoice.evidence(invoices),
            cash_evidence,
            aging.evidence(accounts),
            forecast_evidence,
            credit_evidence,
            collection.evidence(distribution, integrity, accounts, queue.decisions),
        ],
    }
