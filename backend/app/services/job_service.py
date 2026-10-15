from sqlmodel import Session, select

from app.exceptions import NotFoundException
from app.models import AuditActorType, Job, JobStatus
from app.services.audit_service import log_event


def create_job(
    session: Session,
    tenant_id: int,
    title: str,
    description: str,
    status: str | JobStatus = JobStatus.OPEN,
    creator_name: str = "",
) -> Job:
    """Create a new job for the tenant and log an audit entry."""
    status_val = status.value if isinstance(status, JobStatus) else str(status)
    job = Job(
        tenant_id=tenant_id,
        title=title,
        description=description,
        status=JobStatus(status_val) if status_val in ("open", "closed") else JobStatus.OPEN,
    )
    session.add(job)
    session.flush()

    assert job.id is not None
    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=creator_name or "system",
        action="create_job",
        entity_type="job",
        entity_id=job.id,
        details={"title": title},
    )

    session.commit()
    session.refresh(job)
    return job


def list_jobs(session: Session, tenant_id: int) -> list[Job]:
    """List all jobs belonging to the current tenant."""
    statement = (
        select(Job)
        .where(Job.tenant_id == tenant_id)
        .order_by(Job.created_at.desc())
    )
    return list(session.exec(statement).all())


def get_job(session: Session, job_id: int, tenant_id: int) -> Job:
    """Retrieve a job by ID scoped to current tenant, raising NotFoundException otherwise."""
    job = session.get(Job, job_id)
    if not job or job.tenant_id != tenant_id:
        raise NotFoundException(f"Job {job_id} not found")
    return job
