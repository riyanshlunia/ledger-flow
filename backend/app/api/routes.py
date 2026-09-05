"""
API Routes — Reconciliation, Forecasts, Scenarios, Escalations, Audit, Dashboard.
"""
from datetime import date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.session import get_db
from app.models.models import (
    BankTransaction, ERPTransaction, BankAccount,
    ReconciliationMatch, CashFlowForecast, ForecastDriver,
    EscalationEvent, AuditLog, Invoice, Bill, Entity, Scenario, PolicyRule
)
from app.api.schemas import (
    ReconciliationMatchOut, ReconciliationListOut, ReconciliationExplainOut,
    ReviewDecisionIn,
    ForecastListOut, ForecastBucketOut, ForecastDriversOut, ForecastExplainOut,
    ScenarioOut, ScenarioCreateIn, ScenarioDeltaOut, ScenarioDeltaBucket,
    EscalationOut, EscalationDecisionIn, EscalationListOut,
    AuditLogOut, AuditListOut,
    DashboardStatsOut,
)
from app.agents.reconciliation_agent import ReconciliationAgent
from app.agents.forecast_agent import ForecastAgent
from app.agents.governance_agent import GovernanceAgent

router = APIRouter()

DEFAULT_ENTITY = "ENTITY-US-001"


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/dashboard/stats", response_model=DashboardStatsOut, tags=["Dashboard"])
def get_dashboard_stats(
    entity_id: str = Query(DEFAULT_ENTITY),
    db: Session = Depends(get_db),
):
    entity = db.query(Entity).filter_by(id=entity_id).first()
    if not entity:
        raise HTTPException(404, "Entity not found")

    account = db.query(BankAccount).filter_by(entity_id=entity_id, is_active=True).first()

    total_btx = db.query(BankTransaction).join(BankAccount).filter(
        BankAccount.entity_id == entity_id
    ).count()

    def match_count(status):
        return db.query(ReconciliationMatch).filter(
            ReconciliationMatch.entity_id == entity_id,
            ReconciliationMatch.match_status == status,
        ).count()

    matched = db.query(ReconciliationMatch).filter(
        ReconciliationMatch.entity_id == entity_id,
        ReconciliationMatch.match_status.in_(["MATCHED", "HUMAN_CONFIRMED"]),
    ).count()
    pending = match_count("PENDING_REVIEW")
    unmatched = match_count("UNMATCHED")
    total_matches = db.query(ReconciliationMatch).filter_by(entity_id=entity_id).count()
    match_rate = (matched / total_btx * 100) if total_btx > 0 else 0

    open_esc = db.query(EscalationEvent).filter(
        EscalationEvent.entity_id == entity_id,
        EscalationEvent.status == "OPEN",
    ).count()

    ar_total = db.query(func.sum(Invoice.outstanding_amount)).filter(
        Invoice.entity_id == entity_id,
        Invoice.status.in_(["OPEN", "PARTIAL", "OVERDUE"]),
    ).scalar() or 0

    ap_total = db.query(func.sum(Bill.outstanding_amount)).filter(
        Bill.entity_id == entity_id,
        Bill.status.in_(["RECEIVED", "APPROVED", "SCHEDULED"]),
    ).scalar() or 0

    # Next 4 weeks net from latest forecast
    latest_run = (
        db.query(func.max(CashFlowForecast.forecast_run_at))
        .filter(CashFlowForecast.entity_id == entity_id, CashFlowForecast.scenario_id.is_(None))
        .scalar()
    )
    next4_net = 0.0
    if latest_run:
        buckets = (
            db.query(CashFlowForecast)
            .filter(
                CashFlowForecast.entity_id == entity_id,
                CashFlowForecast.scenario_id.is_(None),
                CashFlowForecast.forecast_run_at == latest_run,
                CashFlowForecast.forecast_date >= date.today(),
                CashFlowForecast.forecast_date <= date.today() + timedelta(weeks=4),
            )
            .all()
        )
        next4_net = sum(float(b.net_cash_flow) for b in buckets)

    return DashboardStatsOut(
        entity_id=entity_id,
        entity_name=entity.name,
        current_balance=float(account.current_balance) if account else 0,
        currency=entity.currency,
        balance_as_of=account.balance_as_of if account else None,
        total_bank_transactions=total_btx,
        matched_count=matched,
        pending_review_count=pending,
        unmatched_count=unmatched,
        match_rate_pct=round(match_rate, 1),
        open_escalations=open_esc,
        open_invoices_total=float(ar_total),
        open_bills_total=float(ap_total),
        forecast_next_4_weeks_net=next4_net,
    )


# ─────────────────────────────────────────────────────────────────────────────
# RECONCILIATION
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/reconciliations/run", tags=["Reconciliation"])
def trigger_reconciliation(
    entity_id: str = Query(DEFAULT_ENTITY),
    db: Session = Depends(get_db),
):
    """Trigger the reconciliation agent for an entity."""
    agent = ReconciliationAgent()
    results = agent.run(db, entity_id)
    return {"status": "completed", "results": results}


@router.get("/reconciliations", response_model=ReconciliationListOut, tags=["Reconciliation"])
def list_reconciliations(
    entity_id: str = Query(DEFAULT_ENTITY),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(ReconciliationMatch).filter(ReconciliationMatch.entity_id == entity_id)
    if status:
        q = q.filter(ReconciliationMatch.match_status == status)
    total = q.count()
    items = q.order_by(ReconciliationMatch.matched_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ReconciliationListOut(
        total=total, page=page, page_size=page_size,
        items=[ReconciliationMatchOut(
            match_id=m.id,
            bank_tx_id=m.bank_tx_id,
            erp_tx_id=m.erp_tx_id,
            entity_id=m.entity_id,
            match_status=m.match_status,
            match_method=m.match_method,
            confidence_score=float(m.confidence_score),
            amount_variance=float(m.amount_variance) if m.amount_variance else None,
            natural_language=m.natural_language,
            matched_at=m.matched_at,
            reviewed_by=m.reviewed_by,
            reviewed_at=m.reviewed_at,
        ) for m in items]
    )


@router.get("/reconciliations/{match_id}/explain", response_model=ReconciliationExplainOut, tags=["Reconciliation"])
def explain_reconciliation(match_id: str, db: Session = Depends(get_db)):
    match = db.query(ReconciliationMatch).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")

    bank_tx = db.query(BankTransaction).filter_by(id=match.bank_tx_id).first()
    erp_tx = db.query(ERPTransaction).filter_by(id=match.erp_tx_id).first() if match.erp_tx_id else None

    return ReconciliationExplainOut(
        match_id=match.id,
        confidence_score=float(match.confidence_score),
        match_method=match.match_method,
        feature_scores=match.feature_scores,
        alternatives_considered=match.alternatives_json,
        natural_language=match.natural_language,
        bank_tx={
            "id": bank_tx.id,
            "source_tx_id": bank_tx.source_tx_id,
            "value_date": str(bank_tx.value_date),
            "amount": float(bank_tx.amount),
            "currency": bank_tx.currency,
            "direction": bank_tx.direction,
            "counterparty_name": bank_tx.counterparty_name,
            "reference": bank_tx.reference,
        } if bank_tx else None,
        erp_tx={
            "id": erp_tx.id,
            "source_tx_id": erp_tx.source_tx_id,
            "tx_type": erp_tx.tx_type,
            "transaction_date": str(erp_tx.transaction_date),
            "amount": float(erp_tx.amount),
            "counterparty_name": erp_tx.counterparty_name,
            "reference": erp_tx.reference,
        } if erp_tx else None,
    )


@router.post("/reconciliations/{match_id}/review", tags=["Reconciliation"])
def review_reconciliation(
    match_id: str,
    body: ReviewDecisionIn,
    db: Session = Depends(get_db),
):
    agent = ReconciliationAgent()
    match = agent.review_decision(
        db, match_id, body.decision, body.reviewer, body.note, body.remap_erp_tx_id
    )
    return {"match_id": match.id, "new_status": match.match_status}


# ─────────────────────────────────────────────────────────────────────────────
# FORECASTS
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/forecasts/run", tags=["Forecasts"])
def trigger_forecast(
    entity_id: str = Query(DEFAULT_ENTITY),
    scenario_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Trigger the forecast agent."""
    scenario = db.query(Scenario).filter_by(id=scenario_id).first() if scenario_id else None
    agent = ForecastAgent()
    forecasts = agent.run(db, entity_id, scenario=scenario)

    # Run governance on each bucket
    gov = GovernanceAgent()
    breaches = []
    for f in forecasts:
        b = gov.evaluate_forecast(db, f)
        breaches.extend(b)
    db.commit()

    return {
        "status": "completed",
        "weeks_generated": len(forecasts),
        "policy_breaches": len(breaches),
    }


@router.get("/forecasts/current", response_model=ForecastListOut, tags=["Forecasts"])
def get_current_forecast(
    entity_id: str = Query(DEFAULT_ENTITY),
    scenario_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    account = db.query(BankAccount).filter_by(entity_id=entity_id, is_active=True).first()
    currency = account.currency if account else "USD"

    latest_run = (
        db.query(func.max(CashFlowForecast.forecast_run_at))
        .filter(
            CashFlowForecast.entity_id == entity_id,
            CashFlowForecast.scenario_id == scenario_id if scenario_id else CashFlowForecast.scenario_id.is_(None),
        )
        .scalar()
    )

    if not latest_run:
        return ForecastListOut(
            entity_id=entity_id, currency=currency,
            generated_at=__import__('datetime').datetime.now(),
            is_stale=True, scenario_id=scenario_id, buckets=[]
        )

    buckets = (
        db.query(CashFlowForecast)
        .filter(
            CashFlowForecast.entity_id == entity_id,
            CashFlowForecast.forecast_run_at == latest_run,
            CashFlowForecast.scenario_id == scenario_id if scenario_id else CashFlowForecast.scenario_id.is_(None),
        )
        .order_by(CashFlowForecast.forecast_date)
        .all()
    )

    from datetime import timedelta
    bucket_out = []
    for b in buckets:
        period_end = b.forecast_date + timedelta(days=6)
        bucket_out.append(ForecastBucketOut(
            forecast_id=b.id,
            period_start=b.forecast_date,
            period_end=period_end,
            granularity=b.granularity,
            opening_balance=float(b.opening_balance),
            total_inflows=float(b.total_inflows),
            total_outflows=float(b.total_outflows),
            net_cash_flow=float(b.net_cash_flow),
            closing_balance=float(b.closing_balance),
            p10_closing=float(b.p10_closing),
            p90_closing=float(b.p90_closing),
            model_version=b.model_version,
            is_stale=b.is_stale,
            natural_language=b.natural_language,
        ))

    return ForecastListOut(
        entity_id=entity_id,
        currency=currency,
        generated_at=latest_run,
        is_stale=any(b.is_stale for b in buckets),
        scenario_id=scenario_id,
        buckets=bucket_out,
    )


@router.get("/forecasts/{forecast_id}/drivers", response_model=ForecastDriversOut, tags=["Forecasts"])
def get_forecast_drivers(forecast_id: str, db: Session = Depends(get_db)):
    forecast = db.query(CashFlowForecast).filter_by(id=forecast_id).first()
    if not forecast:
        raise HTTPException(404, "Forecast not found")

    drivers = db.query(ForecastDriver).filter_by(forecast_id=forecast_id).all()
    summary = {}
    driver_out = []
    for d in drivers:
        dt = d.driver_type
        summary[dt] = summary.get(dt, 0) + float(d.amount)
        driver_out.append(ForecastDriverOut(
            driver_id=d.id,
            driver_type=d.driver_type,
            amount=float(d.amount),
            probability=float(d.probability) if d.probability else None,
            source_type=d.source_type,
            source_id=d.invoice_id or d.bill_id,
            counterparty_name=d.counterparty_name,
            expected_date=d.expected_date,
            notes=d.notes,
        ))

    return ForecastDriversOut(
        forecast_id=forecast_id,
        drivers=driver_out,
        summary_by_type=summary,
    )


@router.get("/forecasts/{forecast_id}/explain", response_model=ForecastExplainOut, tags=["Forecasts"])
def explain_forecast(forecast_id: str, db: Session = Depends(get_db)):
    forecast = db.query(CashFlowForecast).filter_by(id=forecast_id).first()
    if not forecast:
        raise HTTPException(404, "Forecast not found")
    return ForecastExplainOut(
        forecast_id=forecast_id,
        natural_language=forecast.natural_language,
        sensitivity={
            "dso_plus_10_days": {"note": "Re-run with SCN-002 (Slow Collections) to see delta"},
            "fx_minus_5pct": {"note": "Re-run with SCN-003 (FX Shock) to see delta"},
        },
        model_version=forecast.model_version,
        data_snapshot_hash=forecast.data_snapshot_hash,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/scenarios", response_model=List[ScenarioOut], tags=["Scenarios"])
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = db.query(Scenario).filter_by(is_active=True).order_by(Scenario.created_at).all()
    return [ScenarioOut(
        scenario_id=s.id,
        name=s.name,
        description=s.description,
        parameters=s.parameters,
        is_system_scenario=s.is_system_scenario,
        created_at=s.created_at,
    ) for s in scenarios]


@router.post("/scenarios", response_model=ScenarioOut, tags=["Scenarios"])
def create_scenario(body: ScenarioCreateIn, db: Session = Depends(get_db)):
    import uuid
    s = Scenario(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        parameters=body.parameters,
        is_system_scenario=False,
    )
    db.add(s)
    db.commit()
    return ScenarioOut(
        scenario_id=s.id,
        name=s.name,
        description=s.description,
        parameters=s.parameters,
        is_system_scenario=s.is_system_scenario,
        created_at=s.created_at,
    )


@router.get("/scenarios/{scenario_id}/delta", response_model=ScenarioDeltaOut, tags=["Scenarios"])
def get_scenario_delta(
    scenario_id: str,
    entity_id: str = Query(DEFAULT_ENTITY),
    db: Session = Depends(get_db),
):
    scenario = db.query(Scenario).filter_by(id=scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    # Get latest base forecast
    base_run = db.query(func.max(CashFlowForecast.forecast_run_at)).filter(
        CashFlowForecast.entity_id == entity_id,
        CashFlowForecast.scenario_id.is_(None),
    ).scalar()

    if not base_run:
        raise HTTPException(404, "No base forecast found. Run /forecasts/run first.")

    base_buckets = (
        db.query(CashFlowForecast)
        .filter(
            CashFlowForecast.entity_id == entity_id,
            CashFlowForecast.forecast_run_at == base_run,
            CashFlowForecast.scenario_id.is_(None),
        )
        .order_by(CashFlowForecast.forecast_date)
        .all()
    )

    # Run scenario forecast
    agent = ForecastAgent()
    scn_forecasts = agent.run(db, entity_id, scenario=scenario)
    db.commit()

    scn_map = {f.forecast_date: f for f in scn_forecasts}

    delta_buckets = []
    total_delta = 0.0
    risk_flags = []

    for base in base_buckets:
        scn = scn_map.get(base.forecast_date)
        if not scn:
            continue
        delta = float(scn.net_cash_flow) - float(base.net_cash_flow)
        total_delta += delta
        pct = (delta / abs(float(base.net_cash_flow)) * 100) if base.net_cash_flow else 0

        breaches = []
        # Check min cash
        min_cash_policy = db.query(PolicyRule).filter_by(id="POL-001").first()
        if min_cash_policy:
            threshold = float(min_cash_policy.logic.get("value", 0))
            if float(scn.closing_balance) < threshold:
                flag = f"MIN_CASH_BREACH: ${float(scn.closing_balance):,.0f} < ${threshold:,.0f} threshold"
                breaches.append(flag)
                if flag not in risk_flags:
                    risk_flags.append(flag)

        delta_buckets.append(ScenarioDeltaBucket(
            period_start=base.forecast_date,
            base_net_flow=float(base.net_cash_flow),
            scenario_net_flow=float(scn.net_cash_flow),
            delta=delta,
            delta_pct=round(pct, 1),
            base_closing=float(base.closing_balance),
            scenario_closing=float(scn.closing_balance),
            policy_breaches=breaches,
        ))

    nl = (
        f"Scenario '{scenario.name}' results in a cumulative net cash flow change of "
        f"${total_delta:+,.0f} over {len(delta_buckets)} weeks. "
        f"{'⚠️ Policy breaches detected: ' + '; '.join(risk_flags) if risk_flags else 'No policy breaches detected.'}"
    )

    return ScenarioDeltaOut(
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        buckets=delta_buckets,
        total_delta=total_delta,
        natural_language=nl,
        risk_flags=risk_flags,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ESCALATIONS
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/escalations", response_model=EscalationListOut, tags=["Escalations"])
def list_escalations(
    entity_id: str = Query(DEFAULT_ENTITY),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(EscalationEvent).filter(EscalationEvent.entity_id == entity_id)
    if status:
        q = q.filter(EscalationEvent.status == status)
    if severity:
        q = q.filter(EscalationEvent.severity == severity)
    total = q.count()
    items = q.order_by(EscalationEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return EscalationListOut(
        total=total, page=page, page_size=page_size,
        items=[EscalationOut(
            escalation_id=e.id,
            entity_id=e.entity_id,
            trigger_type=e.trigger_type,
            severity=e.severity,
            status=e.status,
            natural_language=e.natural_language,
            agent_proposal=e.agent_proposal,
            alternatives_json=e.alternatives_json,
            sla_deadline=e.sla_deadline,
            created_at=e.created_at,
            policy_id=e.policy_id,
            related_entity_type=e.related_entity_type,
            related_entity_id=e.related_entity_id,
        ) for e in items]
    )


@router.get("/escalations/{escalation_id}", response_model=EscalationOut, tags=["Escalations"])
def get_escalation(escalation_id: str, db: Session = Depends(get_db)):
    e = db.query(EscalationEvent).filter_by(id=escalation_id).first()
    if not e:
        raise HTTPException(404, "Escalation not found")
    return EscalationOut(
        escalation_id=e.id, entity_id=e.entity_id, trigger_type=e.trigger_type,
        severity=e.severity, status=e.status, natural_language=e.natural_language,
        agent_proposal=e.agent_proposal, alternatives_json=e.alternatives_json,
        sla_deadline=e.sla_deadline, created_at=e.created_at, policy_id=e.policy_id,
        related_entity_type=e.related_entity_type, related_entity_id=e.related_entity_id,
    )


@router.post("/escalations/{escalation_id}/decisions", tags=["Escalations"])
def resolve_escalation(
    escalation_id: str,
    body: EscalationDecisionIn,
    db: Session = Depends(get_db),
):
    agent = GovernanceAgent()
    esc = agent.resolve_escalation(
        db, escalation_id, body.decision, body.resolved_by, body.action_taken, body.note
    )
    return {"escalation_id": esc.id, "status": esc.status, "resolved_at": esc.resolved_at}


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/audit", response_model=AuditListOut, tags=["Audit"])
def get_audit_log(
    entity_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if event_type:
        q = q.filter(AuditLog.event_type == event_type)
    if agent_id:
        q = q.filter(AuditLog.agent_id == agent_id)

    total = q.count()
    entries = q.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return AuditListOut(
        total=total, page=page, page_size=page_size,
        entries=[AuditLogOut(
            log_id=e.log_id,
            timestamp=e.timestamp,
            event_type=e.event_type,
            agent_id=e.agent_id,
            agent_version=e.agent_version,
            user_id=e.user_id,
            entity_id=e.entity_id,
            input_summary=e.input_summary,
            output_summary=e.output_summary,
            policies_evaluated=e.policies_evaluated,
            policies_breached=e.policies_breached,
            hmac_sig=e.hmac_sig,
            notes=e.notes,
        ) for e in entries]
    )
