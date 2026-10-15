from typing import Any
from sqlmodel import Session, select

from app.exceptions import NotFoundException
from app.models import AuditActorType, Candidate
from app.services.audit_service import log_event


def create_candidate(
    session: Session,
    tenant_id: int,
    full_name: str,
    email: str,
    resume_text: str | None = None,
    parsed_data: dict[str, Any] | None = None,
    creator_name: str = "",
) -> Candidate:
    """Create a candidate under the tenant and log an audit event."""
    candidate = Candidate(
        tenant_id=tenant_id,
        full_name=full_name,
        email=email,
        resume_text=resume_text,
        parsed_data=parsed_data,
    )
    session.add(candidate)
    session.flush()

    assert candidate.id is not None
    # Never log resume text per security rules
    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=creator_name or "system",
        action="create_candidate",
        entity_type="candidate",
        entity_id=candidate.id,
        details={"full_name": full_name, "email": email},
    )

    session.commit()
    session.refresh(candidate)
    return candidate


def list_candidates(session: Session, tenant_id: int) -> list[Candidate]:
    """List all candidates belonging to the tenant."""
    statement = (
        select(Candidate)
        .where(Candidate.tenant_id == tenant_id)
        .order_by(Candidate.created_at.desc())
    )
    return list(session.exec(statement).all())


def get_candidate(session: Session, candidate_id: int, tenant_id: int) -> Candidate:
    """Retrieve a candidate by ID scoped to current tenant, raising NotFoundException otherwise."""
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.tenant_id != tenant_id:
        raise NotFoundException(f"Candidate {candidate_id} not found")
    return candidate
