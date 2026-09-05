"""
Pydantic response schemas for the LedgerFlow API.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


# ── Shared ──────────────────────────────────────────────────────────────────
class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int


# ── Reconciliation ───────────────────────────────────────────────────────────
class FeatureScores(BaseModel):
    amount_similarity: float
    date_proximity: float
    reference_similarity: float
    counterparty_match: float
    weighted_confidence: float


class AlternativeMatch(BaseModel):
    erp_tx_id: str
    erp_source_id: Optional[str] = None
    confidence: float
    rejection_reason: str


class ReconciliationMatchOut(BaseModel):
    match_id: str
    bank_tx_id: str
    erp_tx_id: Optional[str]
    entity_id: str
    match_status: str
    match_method: str
    confidence_score: float
    amount_variance: Optional[float]
    natural_language: Optional[str]
    matched_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ReconciliationExplainOut(BaseModel):
    match_id: str
    confidence_score: float
    match_method: str
    feature_scores: Optional[Dict[str, float]]
    alternatives_considered: Optional[List[Dict]]
    natural_language: Optional[str]
    bank_tx: Optional[Dict]
    erp_tx: Optional[Dict]

    model_config = {"from_attributes": True}


class ReconciliationListOut(PaginatedResponse):
    items: List[ReconciliationMatchOut]


class ReviewDecisionIn(BaseModel):
    decision: str = Field(..., description="CONFIRM | REJECT | REMAP")
    reviewer: str
    note: Optional[str] = None
    remap_erp_tx_id: Optional[str] = None


# ── Forecasts ────────────────────────────────────────────────────────────────
class ForecastDriverOut(BaseModel):
    driver_id: str
    driver_type: str
    amount: float
    probability: Optional[float]
    source_type: Optional[str]
    source_id: Optional[str]
    counterparty_name: Optional[str]
    expected_date: Optional[date]
    notes: Optional[str]

    model_config = {"from_attributes": True}


class ForecastBucketOut(BaseModel):
    forecast_id: str
    period_start: date
    period_end: date
    granularity: str
    opening_balance: float
    total_inflows: float
    total_outflows: float
    net_cash_flow: float
    closing_balance: float
    p10_closing: float
    p90_closing: float
    model_version: str
    is_stale: bool
    natural_language: Optional[str]

    model_config = {"from_attributes": True}


class ForecastListOut(BaseModel):
    entity_id: str
    currency: str
    generated_at: datetime
    is_stale: bool
    scenario_id: Optional[str]
    buckets: List[ForecastBucketOut]


class ForecastDriversOut(BaseModel):
    forecast_id: str
    drivers: List[ForecastDriverOut]
    summary_by_type: Dict[str, float]


class ForecastExplainOut(BaseModel):
    forecast_id: str
    natural_language: Optional[str]
    sensitivity: Optional[Dict[str, Any]]
    model_version: str
    data_snapshot_hash: Optional[str]


# ── Scenarios ────────────────────────────────────────────────────────────────
class ScenarioOut(BaseModel):
    scenario_id: str
    name: str
    description: Optional[str]
    parameters: Dict
    is_system_scenario: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ScenarioCreateIn(BaseModel):
    name: str
    description: Optional[str] = None
    entity_ids: Optional[List[str]] = None
    parameters: Dict = Field(default_factory=dict)


class ScenarioDeltaBucket(BaseModel):
    period_start: date
    base_net_flow: float
    scenario_net_flow: float
    delta: float
    delta_pct: float
    base_closing: float
    scenario_closing: float
    policy_breaches: List[str] = []


class ScenarioDeltaOut(BaseModel):
    scenario_id: str
    scenario_name: str
    buckets: List[ScenarioDeltaBucket]
    total_delta: float
    natural_language: str
    risk_flags: List[str]


# ── Escalations ──────────────────────────────────────────────────────────────
class EscalationOut(BaseModel):
    escalation_id: str
    entity_id: str
    trigger_type: str
    severity: str
    status: str
    natural_language: Optional[str]
    agent_proposal: Optional[Dict]
    alternatives_json: Optional[List]
    sla_deadline: Optional[datetime]
    created_at: datetime
    policy_id: Optional[str]
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]

    model_config = {"from_attributes": True}


class EscalationDecisionIn(BaseModel):
    decision: str = Field(..., description="APPROVE | REJECT | DEFER | OVERRIDE")
    resolved_by: str
    action_taken: Optional[str] = None
    note: Optional[str] = None


class EscalationListOut(PaginatedResponse):
    items: List[EscalationOut]


# ── Audit ────────────────────────────────────────────────────────────────────
class AuditLogOut(BaseModel):
    log_id: str
    timestamp: datetime
    event_type: str
    agent_id: Optional[str]
    agent_version: str
    user_id: Optional[str]
    entity_id: Optional[str]
    input_summary: Optional[Dict]
    output_summary: Optional[Dict]
    policies_evaluated: Optional[List]
    policies_breached: Optional[List]
    hmac_sig: str
    notes: Optional[str]

    model_config = {"from_attributes": True}


class AuditListOut(PaginatedResponse):
    entries: List[AuditLogOut]


# ── Dashboard / Stats ────────────────────────────────────────────────────────
class DashboardStatsOut(BaseModel):
    entity_id: str
    entity_name: str
    current_balance: float
    currency: str
    balance_as_of: Optional[datetime]
    total_bank_transactions: int
    matched_count: int
    pending_review_count: int
    unmatched_count: int
    match_rate_pct: float
    open_escalations: int
    open_invoices_total: float
    open_bills_total: float
    forecast_next_4_weeks_net: float
