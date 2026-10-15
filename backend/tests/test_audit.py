from sqlmodel import Session, select
from app.models import AuditActorType, AuditLog, Tenant
from app.services.audit_service import log_event


def test_log_event_creates_audit_log_row(session: Session) -> None:
    tenant = Tenant(name="Acme Corp")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    assert tenant.id is not None

    details_payload = {"key": "value", "count": 42}
    entry = log_event(
        session=session,
        tenant_id=tenant.id,
        actor_type=AuditActorType.USER,
        actor_name="test_user",
        action="create_job",
        entity_type="job",
        entity_id=10,
        details=details_payload,
    )

    session.commit()

    assert entry.id is not None
    assert entry.tenant_id == tenant.id
    assert entry.actor_type == AuditActorType.USER
    assert entry.actor_name == "test_user"
    assert entry.action == "create_job"
    assert entry.entity_type == "job"
    assert entry.entity_id == 10
    assert entry.details == details_payload
    assert entry.created_at is not None

    persisted = session.exec(select(AuditLog).where(AuditLog.id == entry.id)).first()
    assert persisted is not None
    assert persisted.id == entry.id
    assert persisted.tenant_id == tenant.id
    assert persisted.actor_type == "user"
    assert persisted.actor_name == "test_user"
    assert persisted.action == "create_job"
    assert persisted.entity_type == "job"
    assert persisted.entity_id == 10
    assert persisted.details == details_payload
