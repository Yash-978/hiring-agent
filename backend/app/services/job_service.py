from sqlmodel import Session, select

from app.exceptions import NotFoundException
from app.models import Application, AuditActorType, Candidate, Job, JobStatus
from app.schemas.job import (
    CompareCandidateRead,
    CompareCriterionRead,
    CompareJobRead,
    JobCompareRead,
)
from app.services.audit_service import log_event


def create_job(
    session: Session,
    tenant_id: int,
    title: str,
    description: str,
    status: str | JobStatus = JobStatus.OPEN,
    must_have_skills: list[str] | None = None,
    nice_to_have_skills: list[str] | None = None,
    min_years_experience: float | None = None,
    creator_name: str = "",
) -> Job:
    """Create a new job for the tenant and log an audit entry."""
    status_val = status.value if isinstance(status, JobStatus) else str(status)
    job = Job(
        tenant_id=tenant_id,
        title=title,
        description=description,
        status=JobStatus(status_val) if status_val in ("open", "closed") else JobStatus.OPEN,
        must_have_skills=list(must_have_skills or []),
        nice_to_have_skills=list(nice_to_have_skills or []),
        min_years_experience=min_years_experience,
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


def compare_job_candidates(
    session: Session,
    tenant_id: int,
    job_id: int,
) -> JobCompareRead:
    """Return the job and its analyzed candidates ordered by score (best first)."""
    job = get_job(session=session, job_id=job_id, tenant_id=tenant_id)

    statement = (
        select(Application, Candidate.full_name)
        .join(Candidate, Application.candidate_id == Candidate.id)
        .where(
            Application.tenant_id == tenant_id,
            Application.job_id == job_id,
            Candidate.tenant_id == tenant_id,
        )
        .order_by(Application.score.desc())
    )
    rows = session.exec(statement).all()

    candidates: list[CompareCandidateRead] = []
    for application, full_name in rows:
        # JSON columns store Python None as JSON "null", so the analysis must be
        # filtered in Python rather than with a SQL IS NOT NULL clause.
        if not application.analysis:
            continue
        bundle = application.analysis
        analysis = bundle.get("analysis", {})
        raw_breakdown = bundle.get("breakdown", {})
        breakdown = {
            kind: float(raw_breakdown.get(kind, {}).get("ratio", 0.0))
            for kind in ("must_have", "nice_to_have", "experience")
        }
        criteria = [
            CompareCriterionRead(
                criterion=criterion.get("criterion", ""),
                kind=criterion.get("kind", ""),
                verdict=criterion.get("verdict", ""),
            )
            for criterion in analysis.get("criteria", [])
        ]
        candidates.append(
            CompareCandidateRead(
                application_id=application.id,
                name=full_name,
                score=float(application.score or 0.0),
                recommendation=analysis.get("recommendation", ""),
                confidence=analysis.get("confidence", ""),
                years=(analysis.get("candidate") or {}).get("total_years_experience"),
                breakdown=breakdown,
                criteria=criteria,
            )
        )

    return JobCompareRead(
        job=CompareJobRead(
            id=job.id,
            title=job.title,
            must_have_skills=job.must_have_skills,
            nice_to_have_skills=job.nice_to_have_skills,
        ),
        candidates=candidates,
    )
