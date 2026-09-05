"""
Audit logging utility with HMAC-SHA256 signing for immutability.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from sqlalchemy.orm import Session
from app.models.models import AuditLog
from app.core.config import get_settings

settings = get_settings()
AGENT_VERSION = "1.0.0"


def _compute_hmac(payload: dict) -> str:
    """Compute HMAC-SHA256 signature over the log payload."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    sig = hmac.new(
        settings.secret_key.encode(),
        canonical.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"hmac-sha256:{sig}"


def write_audit_log(
    db: Session,
    event_type: str,
    agent_id: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    input_summary: Optional[Dict[str, Any]] = None,
    output_summary: Optional[Dict[str, Any]] = None,
    policies_evaluated: Optional[List[str]] = None,
    policies_breached: Optional[List[str]] = None,
    data_snapshot_hash: Optional[str] = None,
    notes: Optional[str] = None,
) -> AuditLog:
    """Write an immutable, HMAC-signed audit log entry."""
    payload = {
        "event_type": event_type,
        "agent_id": agent_id,
        "agent_version": AGENT_VERSION,
        "user_id": user_id,
        "entity_id": entity_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_summary": input_summary or {},
        "output_summary": output_summary or {},
        "policies_evaluated": policies_evaluated or [],
        "policies_breached": policies_breached or [],
    }

    log = AuditLog(
        event_type=event_type,
        agent_id=agent_id,
        agent_version=AGENT_VERSION,
        user_id=user_id,
        entity_id=entity_id,
        data_snapshot_hash=data_snapshot_hash,
        input_summary=input_summary,
        output_summary=output_summary,
        policies_evaluated=policies_evaluated,
        policies_breached=policies_breached,
        hmac_sig=_compute_hmac(payload),
        notes=notes,
    )
    db.add(log)
    db.flush()  # get log_id without committing
    return log
