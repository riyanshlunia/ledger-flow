"""
ForecastAgent — AR-driven inflows + AP-driven outflows + rule-based components.
Produces 13-week rolling CashFlowForecast with ForecastDriver attribution
and natural-language explanations.
"""
import hashlib
import json
import random
from datetime import date, datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.models import (
    Invoice, Bill, BankAccount, CashFlowForecast, ForecastDriver, Scenario
)
from app.core.audit import write_audit_log

AGENT_ID = "forecast-agent"
AGENT_VERSION = "1.0.0"
MODEL_VERSION = "ar-ap-rule-v1.0.0"


def _week_start(d: date) -> date:
    """Return the Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def _collection_probability(invoice: Invoice, period_end: date) -> float:
    """
    Estimate probability that invoice will be collected by period_end.
    Uses a sigmoid decay based on days remaining vs due date + avg lateness.
    """
    base = float(invoice.collection_probability)
    days_to_due = (invoice.due_date - period_end).days
    avg_late = float(invoice.avg_days_late)

    # If period_end is after due_date + avg_late, high probability
    if days_to_due + avg_late <= 0:
        return min(base, 0.97)
    # Linear decay if due after period
    decay = max(0.0, 1.0 - (days_to_due + avg_late) / 30.0)
    return round(min(base * decay, 0.97), 4)


def _payment_probability(bill: Bill, period_end: date) -> float:
    """Estimate probability that bill will be paid by period_end."""
    if bill.approval_status == "APPROVED":
        if bill.payment_scheduled_date and bill.payment_scheduled_date <= period_end:
            return 0.98
        if bill.due_date <= period_end:
            return 0.95
        return 0.10
    # PENDING approval
    base_approval = float(bill.approval_probability)
    if bill.due_date <= period_end:
        return base_approval * 0.80
    return 0.05


def _compute_data_hash(entity_id: str, run_at: datetime) -> str:
    payload = f"{entity_id}:{run_at.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _generate_forecast_nl(
    period_start: date,
    period_end: date,
    net_flow: float,
    inflows: float,
    outflows: float,
    p10: float,
    p90: float,
    top_ar: List[Dict],
    top_ap: List[Dict],
) -> str:
    direction = "increase" if net_flow >= 0 else "decrease"
    top_ar_str = ", ".join(
        f"{d['counterparty_name']} (${d['amount']:,.0f}, {d['probability']:.0%})"
        for d in top_ar[:2]
    ) or "no major invoices due"
    top_ap_str = ", ".join(
        f"{d['counterparty_name']} (${abs(d['amount']):,.0f})"
        for d in top_ap[:2]
    ) or "no major bills due"

    risk_note = ""
    for d in top_ar[:3]:
        if d.get("probability", 1.0) < 0.75:
            risk_note = (
                f" Risk: {d['counterparty_name']} collection probability is "
                f"{d['probability']:.0%} — may slip to next period."
            )
            break

    return (
        f"Week of {period_start.strftime('%b %d')} is forecast to show a net cash "
        f"{direction} of ${abs(net_flow):,.0f} (range: ${p10:,.0f}–${p90:,.0f}). "
        f"Key inflows: {top_ar_str}. "
        f"Key outflows: {top_ap_str}.{risk_note}"
    )


class ForecastAgent:
    """
    Rolling 13-week cash flow forecast agent.
    Generates one CashFlowForecast + N ForecastDrivers per week per entity.
    """

    def run(
        self,
        db: Session,
        entity_id: str,
        scenario: Optional[Scenario] = None,
        start_date: Optional[date] = None,
        weeks: int = 13,
    ) -> List[CashFlowForecast]:
        """Generate a 13-week rolling forecast for entity_id."""
        today = start_date or date.today()
        week_start = _week_start(today)
        run_at = datetime.now(timezone.utc)
        snapshot_hash = _compute_data_hash(entity_id, run_at)

        # Get scenario parameters (DSO delta, FX multiplier, etc.)
        params = {}
        if scenario:
            params = scenario.parameters or {}

        dso_delta = int(params.get("dso_delta_days", 0))
        fx_multiplier = float(params.get("fx_multiplier", 1.0))

        # Fetch current balance
        account = db.query(BankAccount).filter_by(entity_id=entity_id, is_active=True).first()
        opening_balance = float(account.current_balance) if account else 5_000_000.0
        currency = account.currency if account else "USD"

        # Fetch open AR invoices
        open_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.entity_id == entity_id,
                Invoice.status.in_(["OPEN", "PARTIAL", "OVERDUE"]),
            )
            .all()
        )

        # Fetch open AP bills
        open_bills = (
            db.query(Bill)
            .filter(
                Bill.entity_id == entity_id,
                Bill.status.in_(["RECEIVED", "APPROVED", "SCHEDULED"]),
            )
            .all()
        )

        forecasts = []
        current_balance = opening_balance

        for week_idx in range(weeks):
            period_start = week_start + timedelta(weeks=week_idx)
            period_end = period_start + timedelta(days=6)
            adjusted_period_end = period_end + timedelta(days=dso_delta)

            # --- AR Inflows ---
            ar_drivers = []
            total_ar = 0.0
            for inv in open_invoices:
                prob = _collection_probability(inv, adjusted_period_end)
                if prob < 0.05:
                    continue
                expected = float(inv.outstanding_amount) * prob * fx_multiplier
                ar_drivers.append({
                    "invoice_id": inv.id,
                    "counterparty_name": inv.customer_name,
                    "amount": expected,
                    "probability": prob,
                    "expected_date": inv.due_date.isoformat(),
                    "driver_type": "AR_INFLOW",
                })
                total_ar += expected
            ar_drivers.sort(key=lambda x: x["amount"], reverse=True)

            # --- AP Outflows ---
            ap_drivers = []
            total_ap = 0.0
            for bill in open_bills:
                prob = _payment_probability(bill, period_end)
                if prob < 0.05:
                    continue
                expected = -float(bill.outstanding_amount) * prob
                ap_drivers.append({
                    "bill_id": bill.id,
                    "counterparty_name": bill.vendor_name,
                    "amount": expected,
                    "probability": prob,
                    "expected_date": bill.due_date.isoformat(),
                    "driver_type": "AP_OUTFLOW",
                })
                total_ap += expected
            ap_drivers.sort(key=lambda x: x["amount"])

            # --- Rule-based: Payroll (bi-weekly on Fridays) ---
            payroll_amount = 0.0
            payroll_day = period_start
            while payroll_day <= period_end:
                if payroll_day.weekday() == 4 and payroll_day.day in range(14, 17):
                    payroll_amount = -params.get("payroll_biweekly", 185_000)
                payroll_day += timedelta(days=1)

            # Net flows
            net_flow = total_ar + total_ap + payroll_amount
            closing = current_balance + net_flow

            # Uncertainty bands (±15% p10/p90)
            p10 = closing * 0.85
            p90 = closing * 1.15

            # Natural language
            nl = _generate_forecast_nl(
                period_start, period_end, net_flow,
                total_ar, total_ap,
                p10, p90,
                ar_drivers[:3], ap_drivers[:3],
            )

            # Persist forecast
            forecast = CashFlowForecast(
                entity_id=entity_id,
                currency=currency,
                forecast_date=period_start,
                forecast_run_at=run_at,
                scenario_id=scenario.id if scenario else None,
                granularity="WEEKLY",
                opening_balance=current_balance,
                total_inflows=total_ar,
                total_outflows=total_ap + payroll_amount,
                net_cash_flow=net_flow,
                closing_balance=closing,
                p10_closing=p10,
                p90_closing=p90,
                model_version=MODEL_VERSION,
                data_snapshot_hash=snapshot_hash,
                natural_language=nl,
            )
            db.add(forecast)
            db.flush()

            # Persist drivers
            for drv in ar_drivers[:10]:
                db.add(ForecastDriver(
                    forecast_id=forecast.id,
                    driver_type="AR_INFLOW",
                    invoice_id=drv["invoice_id"],
                    source_type="INVOICE",
                    amount=drv["amount"],
                    probability=drv["probability"],
                    expected_date=date.fromisoformat(drv["expected_date"]),
                    counterparty_name=drv["counterparty_name"],
                ))
            for drv in ap_drivers[:10]:
                db.add(ForecastDriver(
                    forecast_id=forecast.id,
                    driver_type="AP_OUTFLOW",
                    bill_id=drv.get("bill_id"),
                    source_type="BILL",
                    amount=drv["amount"],
                    probability=drv["probability"],
                    expected_date=date.fromisoformat(drv["expected_date"]),
                    counterparty_name=drv["counterparty_name"],
                ))
            if payroll_amount != 0:
                db.add(ForecastDriver(
                    forecast_id=forecast.id,
                    driver_type="PAYROLL",
                    source_type="SCHEDULED_PAYMENT",
                    amount=payroll_amount,
                    probability=1.0,
                    notes="Bi-weekly payroll (rule-based)",
                ))

            forecasts.append(forecast)
            current_balance = closing

        db.commit()

        write_audit_log(
            db,
            event_type="FORECAST_COMPLETE",
            agent_id=AGENT_ID,
            entity_id=entity_id,
            output_summary={
                "weeks_generated": weeks,
                "scenario_id": scenario.id if scenario else None,
                "model_version": MODEL_VERSION,
                "snapshot_hash": snapshot_hash,
            },
        )
        db.commit()
        return forecasts
