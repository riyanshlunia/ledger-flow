"""
SQLAlchemy ORM Models — LedgerFlow Agent
All financial tables with full audit fields.
"""
import uuid
import hashlib
import json
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column, String, Numeric, Boolean, Date, DateTime,
    ForeignKey, Text, Integer, JSON, ARRAY, UUID as SUUID,
    UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from app.db.session import Base


def gen_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Entity (Company / Business Unit)
# ---------------------------------------------------------------------------
class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    country: Mapped[Optional[str]] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bank_accounts: Mapped[List["BankAccount"]] = relationship(back_populates="entity")
    erp_transactions: Mapped[List["ERPTransaction"]] = relationship(back_populates="entity")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="entity")
    bills: Mapped[List["Bill"]] = relationship(back_populates="entity")
    forecasts: Mapped[List["CashFlowForecast"]] = relationship(back_populates="entity")
    escalations: Mapped[List["EscalationEvent"]] = relationship(back_populates="entity")


# ---------------------------------------------------------------------------
# Bank Account
# ---------------------------------------------------------------------------
class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    iban: Mapped[Optional[str]] = mapped_column(String(34))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), default="CHECKING")
    current_balance: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    balance_as_of: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="bank_accounts")
    transactions: Mapped[List["BankTransaction"]] = relationship(back_populates="bank_account")


# ---------------------------------------------------------------------------
# Bank Transaction (immutable after ingestion)
# ---------------------------------------------------------------------------
class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_bank_tx_fingerprint"),
        Index("ix_bank_tx_account_date", "bank_account_id", "value_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    bank_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("bank_accounts.id"), nullable=False)
    source_tx_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    value_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_date: Mapped[Optional[date]] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # CREDIT / DEBIT
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(200))
    counterparty_iban: Mapped[Optional[str]] = mapped_column(String(34))
    reference: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    transaction_type: Mapped[Optional[str]] = mapped_column(String(50))  # PAYMENT, FEE, INTEREST
    source_format: Mapped[str] = mapped_column(String(20), default="API")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)

    bank_account: Mapped["BankAccount"] = relationship(back_populates="transactions")
    matches: Mapped[List["ReconciliationMatch"]] = relationship(back_populates="bank_transaction")


# ---------------------------------------------------------------------------
# ERP Transaction
# ---------------------------------------------------------------------------
class ERPTransaction(Base):
    __tablename__ = "erp_transactions"
    __table_args__ = (
        Index("ix_erp_tx_entity_date", "entity_id", "transaction_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), default="NETSUITE")
    source_tx_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tx_type: Mapped[str] = mapped_column(String(30), nullable=False)  # AR_RECEIPT, AP_PAYMENT, JOURNAL
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[Optional[date]] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gl_account: Mapped[Optional[str]] = mapped_column(String(50))
    counterparty_id: Mapped[Optional[str]] = mapped_column(String(100))
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(200))
    invoice_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("invoices.id"))
    bill_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bills.id"))
    reference: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="POSTED")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="erp_transactions")
    matches: Mapped[List["ReconciliationMatch"]] = relationship(back_populates="erp_transaction")


# ---------------------------------------------------------------------------
# Invoice (AR)
# ---------------------------------------------------------------------------
class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoice_entity_due", "entity_id", "due_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), default="NETSUITE")
    source_invoice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")  # OPEN, PARTIAL, PAID, OVERDUE
    payment_terms_days: Mapped[Optional[int]] = mapped_column(Integer)
    collection_probability: Mapped[float] = mapped_column(Numeric(5, 4), default=0.85)
    expected_payment_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_payment_date: Mapped[Optional[date]] = mapped_column(Date)
    avg_days_late: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="invoices")
    drivers: Mapped[List["ForecastDriver"]] = relationship(back_populates="invoice")


# ---------------------------------------------------------------------------
# Bill (AP)
# ---------------------------------------------------------------------------
class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        Index("ix_bill_entity_due", "entity_id", "due_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), default="NETSUITE")
    source_bill_id: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED")  # RECEIVED, APPROVED, SCHEDULED, PAID
    approval_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    payment_scheduled_date: Mapped[Optional[date]] = mapped_column(Date)
    approval_probability: Mapped[float] = mapped_column(Numeric(5, 4), default=0.90)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="bills")
    drivers: Mapped[List["ForecastDriver"]] = relationship(back_populates="bill")


# ---------------------------------------------------------------------------
# Reconciliation Match
# ---------------------------------------------------------------------------
class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_matches"
    __table_args__ = (
        Index("ix_recon_status", "match_status"),
        Index("ix_recon_entity", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    bank_tx_id: Mapped[str] = mapped_column(String(36), ForeignKey("bank_transactions.id"), nullable=False)
    erp_tx_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("erp_transactions.id"))
    invoice_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("invoices.id"))
    bill_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bills.id"))
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    match_status: Mapped[str] = mapped_column(String(30), nullable=False)
    # MATCHED, PARTIAL, UNMATCHED, PENDING_REVIEW, HUMAN_CONFIRMED, HUMAN_REJECTED
    match_method: Mapped[str] = mapped_column(String(30), nullable=False)
    # EXACT_RULE, ML_FUZZY, HUMAN
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    amount_variance: Mapped[Optional[float]] = mapped_column(Numeric(20, 6))
    feature_scores: Mapped[Optional[dict]] = mapped_column(JSON)
    alternatives_json: Mapped[Optional[list]] = mapped_column(JSON)
    natural_language: Mapped[Optional[str]] = mapped_column(Text)
    agent_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    model_version: Mapped[Optional[str]] = mapped_column(String(50))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bank_transaction: Mapped["BankTransaction"] = relationship(back_populates="matches")
    erp_transaction: Mapped[Optional["ERPTransaction"]] = relationship(back_populates="matches")


# ---------------------------------------------------------------------------
# Cash Flow Forecast
# ---------------------------------------------------------------------------
class CashFlowForecast(Base):
    __tablename__ = "cash_flow_forecasts"
    __table_args__ = (
        Index("ix_forecast_entity_date", "entity_id", "forecast_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scenario_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("scenarios.id"))
    granularity: Mapped[str] = mapped_column(String(10), default="WEEKLY")
    opening_balance: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    total_inflows: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    total_outflows: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    net_cash_flow: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    closing_balance: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    p10_closing: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    p90_closing: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    model_version: Mapped[str] = mapped_column(String(50), default="v1.0.0")
    data_snapshot_hash: Mapped[Optional[str]] = mapped_column(String(64))
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    stale_reason: Mapped[Optional[str]] = mapped_column(Text)
    natural_language: Mapped[Optional[str]] = mapped_column(Text)

    entity: Mapped["Entity"] = relationship(back_populates="forecasts")
    scenario: Mapped[Optional["Scenario"]] = relationship(back_populates="forecasts")
    drivers: Mapped[List["ForecastDriver"]] = relationship(back_populates="forecast")


# ---------------------------------------------------------------------------
# Forecast Driver
# ---------------------------------------------------------------------------
class ForecastDriver(Base):
    __tablename__ = "forecast_drivers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    forecast_id: Mapped[str] = mapped_column(String(36), ForeignKey("cash_flow_forecasts.id"), nullable=False)
    driver_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # AR_INFLOW, AP_OUTFLOW, PAYROLL, TAX, CAPEX, DEBT_SERVICE, FX_ADJUSTMENT, OTHER
    source_id: Mapped[Optional[str]] = mapped_column(String(36))
    source_type: Mapped[Optional[str]] = mapped_column(String(30))  # INVOICE, BILL, SCHEDULED
    invoice_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("invoices.id"))
    bill_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bills.id"))
    amount: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    probability: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    expected_date: Mapped[Optional[date]] = mapped_column(Date)
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    forecast: Mapped["CashFlowForecast"] = relationship(back_populates="drivers")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="drivers")
    bill: Mapped[Optional["Bill"]] = relationship(back_populates="drivers")


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------
class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(36))
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_system_scenario: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    forecasts: Mapped[List["CashFlowForecast"]] = relationship(back_populates="scenario")


# ---------------------------------------------------------------------------
# Policy Rule
# ---------------------------------------------------------------------------
class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    logic: Mapped[dict] = mapped_column(JSON, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    escalation_target: Mapped[Optional[str]] = mapped_column(String(50))
    sla_hours: Mapped[int] = mapped_column(Integer, default=24)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    escalations: Mapped[List["EscalationEvent"]] = relationship(back_populates="policy")


# ---------------------------------------------------------------------------
# Escalation Event
# ---------------------------------------------------------------------------
class EscalationEvent(Base):
    __tablename__ = "escalation_events"
    __table_args__ = (
        Index("ix_escalation_status", "status"),
        Index("ix_escalation_entity", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # POLICY_BREACH, LOW_CONFIDENCE_MATCH, LARGE_VARIANCE, DATA_QUALITY, UNMATCHED_TRANSACTION
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("policy_rules.id"))
    related_entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    # OPEN, IN_REVIEW, RESOLVED, OVERRIDDEN
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    natural_language: Mapped[Optional[str]] = mapped_column(Text)
    agent_proposal: Mapped[Optional[dict]] = mapped_column(JSON)
    alternatives_json: Mapped[Optional[list]] = mapped_column(JSON)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100))
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="escalations")
    policy: Mapped[Optional["PolicyRule"]] = relationship(back_populates="escalations")


# ---------------------------------------------------------------------------
# Immutable Audit Log
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_event_type", "event_type"),
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_entity", "entity_id"),
    )

    log_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_id: Mapped[Optional[str]] = mapped_column(String(100))
    agent_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    user_id: Mapped[Optional[str]] = mapped_column(String(36))
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    data_snapshot_hash: Mapped[Optional[str]] = mapped_column(String(64))
    input_summary: Mapped[Optional[dict]] = mapped_column(JSON)
    output_summary: Mapped[Optional[dict]] = mapped_column(JSON)
    policies_evaluated: Mapped[Optional[list]] = mapped_column(JSON)
    policies_breached: Mapped[Optional[list]] = mapped_column(JSON)
    hmac_sig: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
