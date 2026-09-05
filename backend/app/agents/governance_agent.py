"""
GovernanceAgent — policy evaluation, escalation management, audit log enforcement.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.models import (
    PolicyRule, EscalationEvent, CashFlowForecast, ReconciliationMatch
)
from app.core.audit import write_audit_log

AGENT_ID = "governance-agent"
AGENT_VERSION = "1.0.0"


class GovernanceAgent:
    """
    Evaluates all active policy rules against agent outputs.
    Creates escalations for breaches.
    """

    def evaluate_forecast(
        self,
        db: Session,
        forecast: CashFlowForecast,
    ) -> List[str]:
        """
        Evaluate all policies against a forecast bucket.
        Returns list of breached policy IDs.
        """
        policies = (
            db.query(PolicyRule)
            .filter(
                PolicyRule.is_active.is_(True),
                PolicyRule.effective_from <= forecast.forecast_date,
            )
            .all()
        )

        breached = []
        evaluated = []

        for policy in policies:
            evaluated.append(policy.id)
            breach = self._evaluate_policy(policy, forecast)
            if breach:
                breached.append(policy.id)
                self._create_policy_escalation(db, policy, forecast)

        write_audit_log(
            db,
            event_type="POLICY_EVALUATED",
            agent_id=AGENT_ID,
            entity_id=forecast.entity_id,
            input_summary={"forecast_id": forecast.id, "period": str(forecast.forecast_date)},
            output_summary={"policies_evaluated": len(evaluated), "breaches": len(breached)},
            policies_evaluated=evaluated,
            policies_breached=breached,
        )

        return breached

    def _evaluate_policy(self, policy: PolicyRule, forecast: CashFlowForecast) -> bool:
        """Evaluate a single policy against a forecast. Returns True if breached."""
        logic = policy.logic
        rule_type = policy.rule_type

        if rule_type == "THRESHOLD":
            field = logic.get("field")
            op = logic.get("operator")
            threshold = float(logic.get("value", 0))

            value = None
            if field == "forecast_closing_balance":
                value = float(forecast.closing_balance)
            elif field == "net_cash_flow":
                value = float(forecast.net_cash_flow)
            elif field == "total_outflows":
                value = float(forecast.total_outflows)

            if value is None:
                return False

            if op == "LESS_THAN":
                return value < threshold
            elif op == "GREATER_THAN":
                return value > threshold
            elif op == "LESS_THAN_OR_EQUAL":
                return value <= threshold

        return False

    def _create_policy_escalation(
        self,
        db: Session,
        policy: PolicyRule,
        forecast: CashFlowForecast,
    ) -> EscalationEvent:
        """Create escalation event for a policy breach."""
        sla_hours = policy.sla_hours or 24
        deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        nl = (
            f"Policy breach detected: '{policy.name}' (v{policy.version}). "
            f"Forecast for {forecast.forecast_date} shows closing balance of "
            f"${float(forecast.closing_balance):,.0f}, which violates the policy threshold. "
            f"Recommended action: {policy.recommended_action or 'Review immediately.'}"
        )

        esc = EscalationEvent(
            entity_id=forecast.entity_id,
            trigger_type="POLICY_BREACH",
            severity=policy.severity,
            policy_id=policy.id,
            related_entity_id=forecast.id,
            related_entity_type="CASH_FLOW_FORECAST",
            status="OPEN",
            sla_deadline=deadline,
            natural_language=nl,
            agent_proposal={
                "action": policy.recommended_action,
                "policy_id": policy.id,
                "policy_name": policy.name,
                "breach_value": float(forecast.closing_balance),
                "threshold": policy.logic.get("value"),
            },
        )
        db.add(esc)
        db.flush()

        write_audit_log(
            db,
            event_type="POLICY_BREACH",
            agent_id=AGENT_ID,
            entity_id=forecast.entity_id,
            input_summary={"policy_id": policy.id, "forecast_id": forecast.id},
            output_summary={"escalation_id": esc.id, "severity": policy.severity},
            policies_breached=[policy.id],
        )
        return esc

    def resolve_escalation(
        self,
        db: Session,
        escalation_id: str,
        decision: str,
        resolved_by: str,
        action_taken: Optional[str] = None,
        note: Optional[str] = None,
    ) -> EscalationEvent:
        """Record human resolution of an escalation."""
        esc = db.query(EscalationEvent).filter_by(id=escalation_id).first()
        if not esc:
            raise ValueError(f"Escalation {escalation_id} not found")

        esc.status = "RESOLVED" if decision in ("APPROVE", "OVERRIDE") else "RESOLVED"
        esc.resolved_by = resolved_by
        esc.resolved_at = datetime.now(timezone.utc)
        esc.resolution_note = note

        write_audit_log(
            db,
            event_type="ESCALATION_RESOLVED",
            agent_id=AGENT_ID,
            user_id=resolved_by,
            entity_id=esc.entity_id,
            input_summary={"escalation_id": escalation_id, "decision": decision},
            output_summary={"action_taken": action_taken, "note": note},
        )
        db.commit()
        return esc
