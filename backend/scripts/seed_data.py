"""
Synthetic data seeder — generates realistic bank statements, ERP transactions,
invoices, bills, and policy rules for demo/testing purposes.
"""
import hashlib
import random
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import date, timedelta, datetime, timezone
from faker import Faker
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.models.models import (
    Base, Entity, BankAccount, BankTransaction, ERPTransaction,
    Invoice, Bill, PolicyRule, Scenario
)

fake = Faker()
random.seed(42)

# ── Customer profiles (controls collection behavior) ──────────────────────
CUSTOMERS = [
    {"id": "CUST-001", "name": "Acme Corporation",     "prob": 0.96, "avg_late": 0,  "terms": 30},
    {"id": "CUST-002", "name": "GlobalTech Industries", "prob": 0.74, "avg_late": 5,  "terms": 45},
    {"id": "CUST-003", "name": "RegionalCo Ltd",        "prob": 0.88, "avg_late": 1,  "terms": 30},
    {"id": "CUST-004", "name": "Meridian Partners",     "prob": 0.91, "avg_late": 2,  "terms": 30},
    {"id": "CUST-005", "name": "Apex Solutions",        "prob": 0.65, "avg_late": 8,  "terms": 60},
    {"id": "CUST-006", "name": "BlueStar Retail",       "prob": 0.82, "avg_late": 3,  "terms": 30},
    {"id": "CUST-007", "name": "Quantum Dynamics",      "prob": 0.95, "avg_late": 0,  "terms": 15},
    {"id": "CUST-008", "name": "Horizon Ventures",      "prob": 0.70, "avg_late": 6,  "terms": 45},
]

VENDORS = [
    {"id": "VEND-001", "name": "Supplier Alpha",     "category": "raw_materials"},
    {"id": "VEND-002", "name": "CloudBase Services", "category": "saas"},
    {"id": "VEND-003", "name": "Logistics Express",  "category": "logistics"},
    {"id": "VEND-004", "name": "Office Supplies Co", "category": "office"},
    {"id": "VEND-005", "name": "Manufacturing Corp", "category": "manufacturing"},
    {"id": "VEND-006", "name": "Tech Solutions Inc", "category": "it_services"},
]


def _fingerprint(account_id: str, tx_id: str, dt: date, amount: float) -> str:
    raw = f"{account_id}:{tx_id}:{dt}:{amount:.2f}"
    return hashlib.sha256(raw.encode()).hexdigest()


def seed(db: Session):
    print("🌱 Creating tables...")
    Base.metadata.create_all(bind=engine)

    print("🏢 Seeding entity...")
    entity = Entity(
        id="ENTITY-US-001",
        name="LedgerFlow Demo Corp (US)",
        currency="USD",
        country="US",
    )
    db.merge(entity)
    db.flush()

    print("🏦 Seeding bank account...")
    account = BankAccount(
        id="ACCT-MAIN-001",
        entity_id=entity.id,
        bank_name="First National Bank",
        account_number="****-4892",
        currency="USD",
        account_type="CHECKING",
        current_balance=8_420_000.00,
        balance_as_of=datetime.now(timezone.utc),
    )
    db.merge(account)
    db.flush()

    today = date.today()
    start = today - timedelta(days=90)

    # ── Historical Bank Transactions (last 90 days, matched to ERP) ──────
    print("💳 Seeding bank transactions + ERP receipts (90 days history)...")
    for i in range(120):
        tx_date = start + timedelta(days=random.randint(0, 85))
        cust = random.choice(CUSTOMERS)
        amount = round(random.uniform(15_000, 950_000), 2)
        ref = f"INV-{1000 + i:04d}"
        tx_id = f"BTX-HIST-{i:04d}"
        fp = _fingerprint("ACCT-MAIN-001", tx_id, tx_date, amount)

        btx = BankTransaction(
            bank_account_id=account.id,
            source_tx_id=tx_id,
            fingerprint=fp,
            value_date=tx_date,
            booking_date=tx_date,
            amount=amount,
            currency="USD",
            direction="CREDIT",
            counterparty_name=cust["name"],
            reference=ref,
            description=f"Payment from {cust['name']}",
            transaction_type="PAYMENT",
            source_format="API",
        )
        db.add(btx)
        db.flush()

        erp = ERPTransaction(
            entity_id=entity.id,
            source_system="NETSUITE",
            source_tx_id=f"ERP-AR-{i:04d}",
            tx_type="AR_RECEIPT",
            transaction_date=tx_date,
            posting_date=tx_date,
            amount=amount,
            currency="USD",
            gl_account="1100",
            counterparty_id=cust["id"],
            counterparty_name=cust["name"],
            reference=ref,
            description=f"AR Receipt {ref}",
            status="POSTED",
        )
        db.add(erp)

    # ── Unmatched bank transactions (exceptions for demo) ────────────────
    print("⚠️  Seeding unmatched/exception bank transactions...")
    for i in range(15):
        tx_date = today - timedelta(days=random.randint(1, 10))
        amount = round(random.uniform(5_000, 200_000), 2)
        tx_id = f"BTX-EXCEPT-{i:04d}"
        fp = _fingerprint("ACCT-MAIN-001", tx_id, tx_date, amount)

        btx = BankTransaction(
            bank_account_id=account.id,
            source_tx_id=tx_id,
            fingerprint=fp,
            value_date=tx_date,
            booking_date=tx_date,
            amount=amount,
            currency="USD",
            direction="CREDIT" if i % 3 != 0 else "DEBIT",
            counterparty_name=f"Unknown Counterparty {i}",
            reference=f"REF-{fake.bothify('??##??##')}",
            description="Wire transfer",
            transaction_type="PAYMENT",
            source_format="MT940",
        )
        db.add(btx)

    # ── Open Invoices (AR, next 13 weeks) ────────────────────────────────
    print("📄 Seeding open invoices (AR)...")
    for i, cust in enumerate(CUSTOMERS):
        # 2–4 invoices per customer
        for j in range(random.randint(2, 4)):
            inv_date = today - timedelta(days=random.randint(0, 20))
            due_date = inv_date + timedelta(days=cust["terms"] + random.randint(-5, 10))
            amount = round(random.uniform(50_000, 900_000), 2)
            inv_id = f"INV-{2000 + i * 10 + j:04d}"

            inv = Invoice(
                entity_id=entity.id,
                source_system="NETSUITE",
                source_invoice_id=inv_id,
                customer_id=cust["id"],
                customer_name=cust["name"],
                invoice_date=inv_date,
                due_date=due_date,
                amount=amount,
                currency="USD",
                outstanding_amount=amount,
                status="OPEN" if due_date >= today else "OVERDUE",
                payment_terms_days=cust["terms"],
                collection_probability=cust["prob"],
                expected_payment_date=due_date + timedelta(days=cust["avg_late"]),
                avg_days_late=cust["avg_late"],
            )
            db.add(inv)

    # ── Open Bills (AP, next 13 weeks) ───────────────────────────────────
    print("📋 Seeding open bills (AP)...")
    for i, vendor in enumerate(VENDORS):
        for j in range(random.randint(1, 3)):
            bill_date = today - timedelta(days=random.randint(0, 15))
            due_date = bill_date + timedelta(days=random.randint(15, 45))
            amount = round(random.uniform(20_000, 500_000), 2)
            bill_id = f"BILL-{3000 + i * 10 + j:04d}"
            approved = random.random() > 0.3

            bill = Bill(
                entity_id=entity.id,
                source_system="NETSUITE",
                source_bill_id=bill_id,
                vendor_id=vendor["id"],
                vendor_name=vendor["name"],
                bill_date=bill_date,
                due_date=due_date,
                amount=amount,
                currency="USD",
                outstanding_amount=amount,
                status="APPROVED" if approved else "RECEIVED",
                approval_status="APPROVED" if approved else "PENDING",
                payment_scheduled_date=due_date if approved else None,
                approval_probability=0.95 if approved else 0.75,
            )
            db.add(bill)

    # ── Policy Rules ─────────────────────────────────────────────────────
    print("📜 Seeding policy rules...")
    policies = [
        PolicyRule(
            id="POL-001",
            name="Minimum Cash Buffer",
            version="1.2",
            effective_from=date(2026, 1, 1),
            rule_type="THRESHOLD",
            logic={"operator": "LESS_THAN", "field": "forecast_closing_balance", "value": 2_000_000},
            severity="CRITICAL",
            escalation_target="treasury_manager",
            sla_hours=4,
            recommended_action="Review revolver availability or defer non-critical payments. Consider drawing on the revolving credit facility.",
        ),
        PolicyRule(
            id="POL-002",
            name="Low Cash Warning",
            version="1.0",
            effective_from=date(2026, 1, 1),
            rule_type="THRESHOLD",
            logic={"operator": "LESS_THAN", "field": "forecast_closing_balance", "value": 5_000_000},
            severity="HIGH",
            escalation_target="treasury_manager",
            sla_hours=24,
            recommended_action="Monitor closely. Accelerate collections or defer discretionary spend.",
        ),
        PolicyRule(
            id="POL-003",
            name="Large Outflow Alert",
            version="1.0",
            effective_from=date(2026, 1, 1),
            rule_type="THRESHOLD",
            logic={"operator": "GREATER_THAN", "field": "total_outflows", "value": 3_000_000},
            severity="MEDIUM",
            escalation_target="controller",
            sla_hours=48,
            recommended_action="Confirm large outflow is approved and documented.",
        ),
    ]
    for p in policies:
        db.merge(p)

    # ── Scenarios ─────────────────────────────────────────────────────────
    print("🎭 Seeding scenarios...")
    scenarios = [
        Scenario(
            id="SCN-001",
            name="Base Case",
            description="No parameter adjustments — standard forecast",
            parameters={},
            is_system_scenario=True,
        ),
        Scenario(
            id="SCN-002",
            name="Slow Collections (+10 Days DSO)",
            description="All customer collections delayed by 10 days",
            parameters={"dso_delta_days": 10},
            is_system_scenario=True,
        ),
        Scenario(
            id="SCN-003",
            name="FX Shock (−5% USD strengthening)",
            description="Apply 5% negative FX multiplier to all inflows",
            parameters={"fx_multiplier": 0.95},
            is_system_scenario=True,
        ),
        Scenario(
            id="SCN-004",
            name="Stressed: Slow Collections + FX",
            description="Combined DSO delay and FX shock",
            parameters={"dso_delta_days": 10, "fx_multiplier": 0.95},
            is_system_scenario=True,
        ),
    ]
    for s in scenarios:
        db.merge(s)

    db.commit()
    print("✅ Seed complete!")
    print(f"   Entity:      {entity.name}")
    print(f"   Bank acct:   {account.bank_name} {account.account_number}")
    print(f"   Balance:     ${account.current_balance:,.2f}")
    print(f"   Invoices:    {sum(1 for _ in db.query(Invoice).filter_by(entity_id=entity.id))}")
    print(f"   Bills:       {sum(1 for _ in db.query(Bill).filter_by(entity_id=entity.id))}")
    print(f"   Bank TXs:    {sum(1 for _ in db.query(BankTransaction))}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
