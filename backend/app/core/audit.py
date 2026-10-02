import logging
import uuid
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.models.audit_log import AuditLog
from app.models.enums import AuditActionType

logger = logging.getLogger("skypulse.audit")


async def log_audit_event(
    db: AsyncSession,
    action_type: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> Optional[AuditLog]:
    """Helper to record audit trail entries in PostgreSQL."""
    try:
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        import time
        audit_id = int(time.time_ns() % (2**53 - 1))

        audit_entry = AuditLog(
            id=audit_id,
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_entry)
        await db.flush()
        return audit_entry
    except Exception as e:
        logger.warning("Failed to record audit log: %s", e)
        return None
