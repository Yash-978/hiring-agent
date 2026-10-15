from typing import Any
from sqlmodel import Session
from app.models import AuditActorType, AuditLog


def log_event(
    session: Session,
    tenant_id: int,
    actor_type: AuditActorType | str,
    actor_name: str,
    action: str,
    entity_type: str,
    entity_id: int,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Create and flush an append-only AuditLog record.
    
    The caller is responsible for committing the session.
    """
    actor_type_val = (
        actor_type.value if isinstance(actor_type, AuditActorType) else actor_type
    )
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_type=AuditActorType(actor_type_val),
        actor_name=actor_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.add(entry)
    session.flush()
    return entry
