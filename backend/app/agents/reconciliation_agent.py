"""
ReconciliationAgent — Tier 1 (exact rule) + Tier 2 (fuzzy ML) matching
with confidence scoring, explanation generation, and exception routing.
"""
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from rapidfuzz import fuzz
from app.models.models import (
    BankTransaction, ERPTransaction, ReconciliationMatch,
    EscalationEvent, PolicyRule, Entity
)
from app.core.audit import write_audit_log

AGENT_ID = "reconciliation-agent"
AGENT_VERSION = "1.0.0"

# Thresholds
TIER1_CONFIDENCE = 0.98
TIER2_HIGH_CONFIDENCE = 0.80
TIER2_MEDIUM_CONFIDENCE = 0.50
DATE_WINDOW_DAYS = 5
AMOUNT_TOLERANCE_PCT = 0.01  # 1%


def _amount_similarity(a: float, b: float) -> float:
    """Similarity score between two amounts. 1.0 = exact."""
    if a == 0 and b == 0:
        return 1.0
    diff = abs(a - b)
    avg = (abs(a) + abs(b)) / 2
    if avg == 0:
        return 0.0
    ratio = diff / avg
    # Exponential decay: 0 diff → 1.0, 10% diff → ~0.37
    return math.exp(-ratio * 10)


def _date_proximity(d1, d2, max_days: int = DATE_WINDOW_DAYS) -> float:
    """Score 1.0 at same date, decays to 0 at max_days+1."""
    if d1 is None or d2 is None:
        return 0.5
    diff = abs((d1 - d2).days)
    if diff > max_days:
        return 0.0
    return 1.0 - (diff / (max_days + 1))


def _reference_similarity(r1: Optional[str], r2: Optional[str]) -> float:
    """Jaro-Winkler similarity on references. 0.5 if either is None."""
    if not r1 or not r2:
        return 0.5
    return fuzz.token_sort_ratio(r1.lower(), r2.lower()) / 100.0


def _counterparty_similarity(cp1: Optional[str], cp2: Optional[str]) -> float:
    """Partial ratio on counterparty names."""
    if not cp1 or not cp2:
        return 0.5
    return fuzz.partial_ratio(cp1.lower(), cp2.lower()) / 100.0


def _compute_confidence(
    bank_tx: BankTransaction,
    erp_tx: ERPTransaction,
) -> Tuple[float, Dict[str, float]]:
    """Compute weighted confidence score and feature breakdown."""
    amount_score = _amount_similarity(float(bank_tx.amount), float(erp_tx.amount))
    date_score = _date_proximity(bank_tx.value_date, erp_tx.transaction_date)
    ref_score = _reference_similarity(bank_tx.reference, erp_tx.reference)
    cp_score = _counterparty_similarity(bank_tx.counterparty_name, erp_tx.counterparty_name)

    # Weighted sum
    confidence = (
        amount_score * 0.40 +
        date_score   * 0.20 +
        ref_score    * 0.25 +
        cp_score     * 0.15
    )

    features = {
        "amount_similarity": round(amount_score, 4),
        "date_proximity": round(date_score, 4),
        "reference_similarity": round(ref_score, 4),
        "counterparty_match": round(cp_score, 4),
        "weighted_confidence": round(confidence, 4),
    }
    return round(confidence, 4), features


def _is_exact_match(bank_tx: BankTransaction, erp_tx: ERPTransaction) -> bool:
    """Tier 1: Exact rule-based match."""
    amount_match = abs(float(bank_tx.amount) - float(erp_tx.amount)) < 0.01
    date_match = abs((bank_tx.value_date - erp_tx.transaction_date).days) <= 2
    ref_match = (
        bank_tx.reference and erp_tx.reference and
        bank_tx.reference.strip().lower() == erp_tx.reference.strip().lower()
    )
    return amount_match and date_match and bool(ref_match)


def _generate_explanation(
    bank_tx: BankTransaction,
    erp_tx: Optional[ERPTransaction],
    confidence: float,
    method: str,
    features: Dict[str, float],
    alternatives: List[Dict],
    status: str,
) -> str:
    """Generate natural language explanation for a match decision."""
    if status == "UNMATCHED":
        return (
            f"Bank transaction #{bank_tx.source_tx_id} "
            f"({bank_tx.direction} {bank_tx.currency} {float(bank_tx.amount):,.2f} "
            f"from '{bank_tx.counterparty_name}' on {bank_tx.value_date}) "
            f"could not be matched to any ERP transaction. "
            f"{len(alternatives)} candidates were considered but all scored below the "
            f"50% confidence threshold. Manual review required."
        )

    alt_note = ""
    if alternatives:
        top_alt = alternatives[0]
        alt_note = (
            f" {len(alternatives)} alternative match(es) were considered and rejected "
            f"(best alternative: {top_alt.get('rejection_reason', 'low confidence')})."
        )

    return (
        f"Bank transaction #{bank_tx.source_tx_id} "
        f"({bank_tx.direction} {bank_tx.currency} {float(bank_tx.amount):,.2f} "
        f"from '{bank_tx.counterparty_name}' on {bank_tx.value_date}) "
        f"was matched to ERP #{erp_tx.source_tx_id} "
        f"with {confidence * 100:.0f}% confidence using {method}. "
        f"Feature scores — amount: {features['amount_similarity']:.0%}, "
        f"date proximity: {features['date_proximity']:.0%}, "
        f"reference: {features['reference_similarity']:.0%}, "
        f"counterparty: {features['counterparty_match']:.0%}.{alt_note}"
    )


def _create_escalation(
    db: Session,
    bank_tx: BankTransaction,
    entity_id: str,
    match_id: str,
    confidence: float,
    trigger_type: str,
    severity: str,
    alternatives: List[Dict],
) -> EscalationEvent:
    """Create an escalation event for human review."""
    from datetime import timezone
    sla_hours = 24 if severity == "HIGH" else 72
    deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

    nl = (
        f"Bank transaction #{bank_tx.source_tx_id} "
        f"({bank_tx.direction} {bank_tx.currency} {float(bank_tx.amount):,.2f} "
        f"from '{bank_tx.counterparty_name}') requires human review. "
        f"Agent confidence: {confidence * 100:.0f}%. "
        f"Trigger: {trigger_type}. Please confirm or remap."
    )

    esc = EscalationEvent(
        entity_id=entity_id,
        trigger_type=trigger_type,
        severity=severity,
        related_entity_id=match_id,
        related_entity_type="RECONCILIATION_MATCH",
        status="OPEN",
        sla_deadline=deadline,
        natural_language=nl,
        agent_proposal={
            "action": "REVIEW_AND_CONFIRM",
            "match_id": match_id,
            "agent_confidence": confidence,
        },
        alternatives_json=alternatives[:3],
    )
    db.add(esc)
    return esc


class ReconciliationAgent:
    """
    Autonomous reconciliation agent.

    Tier 1: Exact rule match (confidence ≥ 0.98) → AUTO_CONFIRMED
    Tier 2: ML fuzzy match ≥ 0.80               → AUTO_CONFIRMED
    Tier 3: Score 0.50–0.79                      → PENDING_REVIEW + escalation
    Tier 4: Score < 0.50                         → UNMATCHED + escalation
    """

    def run(self, db: Session, entity_id: str) -> Dict[str, Any]:
        """Process all unmatched bank transactions for an entity."""
        from sqlalchemy import and_, not_, exists, select

        # Fetch unprocessed bank transactions
        matched_bank_ids = db.query(ReconciliationMatch.bank_tx_id).subquery()
        bank_txs = (
            db.query(BankTransaction)
            .join(BankTransaction.bank_account)
            .filter(
                BankTransaction.bank_account.has(entity_id=entity_id),
                BankTransaction.is_duplicate.is_(False),
                ~BankTransaction.id.in_(matched_bank_ids),
            )
            .all()
        )

        # Fetch available ERP transactions (unmatched)
        matched_erp_ids = db.query(ReconciliationMatch.erp_tx_id).filter(
            ReconciliationMatch.erp_tx_id.isnot(None)
        ).subquery()
        erp_txs = (
            db.query(ERPTransaction)
            .filter(
                ERPTransaction.entity_id == entity_id,
                ERPTransaction.status == "POSTED",
                ~ERPTransaction.id.in_(matched_erp_ids),
            )
            .all()
        )

        results = {
            "auto_confirmed": 0,
            "pending_review": 0,
            "unmatched": 0,
            "total_processed": len(bank_txs),
            "escalations_created": 0,
        }

        for bank_tx in bank_txs:
            match, esc = self._process_single(db, bank_tx, erp_txs, entity_id)
            if match.match_status in ("MATCHED", "AUTO_CONFIRMED"):
                results["auto_confirmed"] += 1
            elif match.match_status == "PENDING_REVIEW":
                results["pending_review"] += 1
            else:
                results["unmatched"] += 1
            if esc:
                results["escalations_created"] += 1

        db.commit()

        write_audit_log(
            db,
            event_type="RECONCILIATION_RUN",
            agent_id=AGENT_ID,
            entity_id=entity_id,
            output_summary=results,
        )
        db.commit()
        return results

    def _process_single(
        self,
        db: Session,
        bank_tx: BankTransaction,
        erp_txs: List[ERPTransaction],
        entity_id: str,
    ) -> Tuple[ReconciliationMatch, Optional[EscalationEvent]]:
        """Score all ERP candidates against a single bank transaction."""
        candidates: List[Tuple[float, Dict, ERPTransaction]] = []

        for erp_tx in erp_txs:
            # Skip direction mismatch (CREDIT bank = AR receipt in ERP)
            if bank_tx.direction == "CREDIT" and erp_tx.tx_type not in ("AR_RECEIPT", "JOURNAL"):
                continue
            if bank_tx.direction == "DEBIT" and erp_tx.tx_type not in ("AP_PAYMENT", "JOURNAL"):
                continue

            # Tier 1: exact match fast path
            if _is_exact_match(bank_tx, erp_tx):
                conf = TIER1_CONFIDENCE
                features = {
                    "amount_similarity": 1.0,
                    "date_proximity": 1.0,
                    "reference_similarity": 1.0,
                    "counterparty_match": 1.0,
                    "weighted_confidence": conf,
                }
                candidates.append((conf, features, erp_tx))
                break  # Exact match wins immediately

            conf, features = _compute_confidence(bank_tx, erp_tx)
            candidates.append((conf, features, erp_tx))

        # Sort candidates descending by confidence
        candidates.sort(key=lambda x: x[0], reverse=True)

        alternatives = []
        if len(candidates) > 1:
            for conf, feat, erp in candidates[1:4]:
                alternatives.append({
                    "erp_tx_id": erp.id,
                    "erp_source_id": erp.source_tx_id,
                    "confidence": conf,
                    "rejection_reason": self._rejection_reason(conf, feat),
                })

        esc = None

        if not candidates:
            # No candidates at all
            match = self._create_match(
                db, bank_tx, None, entity_id,
                "UNMATCHED", "EXACT_RULE", 0.0, {}, [], None
            )
            esc = _create_escalation(
                db, bank_tx, entity_id, match.id,
                0.0, "UNMATCHED_TRANSACTION", "HIGH", []
            )
        else:
            top_conf, top_feat, top_erp = candidates[0]

            if top_conf >= TIER2_HIGH_CONFIDENCE:
                method = "EXACT_RULE" if top_conf >= TIER1_CONFIDENCE else "ML_FUZZY"
                match = self._create_match(
                    db, bank_tx, top_erp, entity_id,
                    "MATCHED", method, top_conf, top_feat, alternatives, top_erp.id
                )
                write_audit_log(
                    db, "RECONCILIATION_MATCH", agent_id=AGENT_ID, entity_id=entity_id,
                    input_summary={"bank_tx_id": bank_tx.id, "erp_tx_id": top_erp.id},
                    output_summary={"match_id": match.id, "confidence": top_conf, "status": "MATCHED"},
                )

            elif top_conf >= TIER2_MEDIUM_CONFIDENCE:
                match = self._create_match(
                    db, bank_tx, top_erp, entity_id,
                    "PENDING_REVIEW", "ML_FUZZY", top_conf, top_feat, alternatives, top_erp.id
                )
                esc = _create_escalation(
                    db, bank_tx, entity_id, match.id,
                    top_conf, "LOW_CONFIDENCE_MATCH", "MEDIUM", alternatives
                )

            else:
                match = self._create_match(
                    db, bank_tx, None, entity_id,
                    "UNMATCHED", "ML_FUZZY", top_conf, top_feat, alternatives, None
                )
                esc = _create_escalation(
                    db, bank_tx, entity_id, match.id,
                    top_conf, "UNMATCHED_TRANSACTION", "HIGH", alternatives
                )

        db.add(match)
        if esc:
            db.add(esc)
        db.flush()
        return match, esc

    def _create_match(
        self,
        db: Session,
        bank_tx: BankTransaction,
        erp_tx: Optional[ERPTransaction],
        entity_id: str,
        status: str,
        method: str,
        confidence: float,
        features: Dict,
        alternatives: List,
        erp_tx_id: Optional[str],
    ) -> ReconciliationMatch:
        nl = _generate_explanation(bank_tx, erp_tx, confidence, method, features, alternatives, status)
        variance = None
        if erp_tx:
            variance = float(bank_tx.amount) - float(erp_tx.amount)

        return ReconciliationMatch(
            bank_tx_id=bank_tx.id,
            erp_tx_id=erp_tx_id,
            entity_id=entity_id,
            match_status=status,
            match_method=method,
            confidence_score=confidence,
            amount_variance=variance,
            feature_scores=features,
            alternatives_json=alternatives,
            natural_language=nl,
            agent_version=AGENT_VERSION,
            model_version="rule+rapidfuzz-v1",
        )

    def _rejection_reason(self, conf: float, features: Dict) -> str:
        if features.get("date_proximity", 1.0) < 0.3:
            return "date_gap_exceeds_5_days"
        if features.get("counterparty_match", 1.0) < 0.4:
            return "counterparty_mismatch"
        if features.get("amount_similarity", 1.0) < 0.5:
            return "amount_variance_too_large"
        return f"overall_confidence_too_low ({conf:.0%})"

    def review_decision(
        self,
        db: Session,
        match_id: str,
        decision: str,
        reviewer: str,
        note: Optional[str] = None,
        remap_erp_tx_id: Optional[str] = None,
    ) -> ReconciliationMatch:
        """Process human review decision on a pending match."""
        match = db.query(ReconciliationMatch).filter_by(id=match_id).first()
        if not match:
            raise ValueError(f"Match {match_id} not found")

        if decision == "CONFIRM":
            match.match_status = "HUMAN_CONFIRMED"
        elif decision == "REJECT":
            match.match_status = "HUMAN_REJECTED"
        elif decision == "REMAP" and remap_erp_tx_id:
            match.erp_tx_id = remap_erp_tx_id
            match.match_status = "HUMAN_CONFIRMED"
            match.match_method = "HUMAN"
            match.confidence_score = 1.0

        match.reviewed_by = reviewer
        match.reviewed_at = datetime.now(timezone.utc)
        match.review_note = note

        write_audit_log(
            db,
            event_type="RECONCILIATION_REVIEW",
            agent_id=AGENT_ID,
            user_id=reviewer,
            entity_id=match.entity_id,
            input_summary={"match_id": match_id, "decision": decision},
            output_summary={"new_status": match.match_status},
        )
        db.commit()
        return match
