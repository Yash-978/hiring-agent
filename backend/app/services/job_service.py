import logging
import re

from sqlalchemy import func, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.exceptions import ConflictException, NotFoundException
from app.models import Application, AuditActorType, Candidate, Job, JobStatus
from app.schemas.job import (
    CompareCandidateRead,
    CompareCountsRead,
    CompareCriterionRead,
    CompareJobRead,
    JobCompareRead,
    JobUpdate,
)
from app.services.audit_service import log_event

logger = logging.getLogger(__name__)

# Name of the per-tenant unique index on job titles.
JOB_TITLE_INDEX_NAME = "ix_job_tenant_title_key"

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Casefold and collapse whitespace so titles compare case/space-insensitively.

    "  Mobile   App Developer " and "mobile app developer" both become
    "mobile app developer".
    """
    return _WHITESPACE_RE.sub(" ", title.strip()).casefold()


def _find_job_by_title_key(
    session: Session,
    tenant_id: int,
    title_key: str,
    exclude_job_id: int | None = None,
) -> Job | None:
    """Return an existing job in the tenant with this title key, if any."""
    statement = select(Job).where(
        Job.tenant_id == tenant_id,
        Job.title_key == title_key,
    )
    for job in session.exec(statement).all():
        if exclude_job_id is None or job.id != exclude_job_id:
            return job
    return None


def _raise_duplicate_title(existing_job_id: int | None) -> None:
    payload: dict[str, object] = {}
    if existing_job_id is not None:
        payload["existing_job_id"] = existing_job_id
    raise ConflictException("A job with this title already exists", payload=payload)


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
    """Create a new job for the tenant and log an audit entry.

    Raises ConflictException if the tenant already has a job with the same
    normalized title.
    """
    status_val = status.value if isinstance(status, JobStatus) else str(status)
    title_key = normalize_title(title)
    existing = _find_job_by_title_key(session, tenant_id, title_key)
    if existing is not None:
        _raise_duplicate_title(existing.id)

    job = Job(
        tenant_id=tenant_id,
        title=title,
        title_key=title_key,
        description=description,
        status=JobStatus(status_val) if status_val in ("open", "closed") else JobStatus.OPEN,
        must_have_skills=list(must_have_skills or []),
        nice_to_have_skills=list(nice_to_have_skills or []),
        min_years_experience=min_years_experience,
    )
    session.add(job)
    try:
        session.flush()
    except IntegrityError as exc:
        # The unique index caught a concurrent insert that the pre-check missed.
        session.rollback()
        raise ConflictException("A job with this title already exists") from exc

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


def update_job(
    session: Session,
    tenant_id: int,
    job_id: int,
    data: JobUpdate,
    actor_name: str = "",
) -> Job:
    """Apply a partial update to a tenant-scoped job and log an audit entry."""
    job = get_job(session=session, job_id=job_id, tenant_id=tenant_id)
    updates = data.model_dump(exclude_unset=True)

    # Required-ish fields cannot be cleared with an explicit null.
    for field in ("title", "description", "status", "must_have_skills", "nice_to_have_skills"):
        if updates.get(field) is None:
            updates.pop(field, None)

    if "title" in updates:
        new_key = normalize_title(str(updates["title"]))
        existing = _find_job_by_title_key(
            session, tenant_id, new_key, exclude_job_id=job.id
        )
        if existing is not None:
            _raise_duplicate_title(existing.id)
        job.title_key = new_key

    if "status" in updates:
        status_val = str(updates["status"])
        job.status = JobStatus(status_val) if status_val in ("open", "closed") else job.status
        updates.pop("status")

    for field, value in updates.items():
        setattr(job, field, value)

    session.add(job)
    session.flush()
    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=actor_name or "system",
        action="update_job",
        entity_type="job",
        entity_id=job.id,
        details={"fields": sorted(updates)},
    )
    session.commit()
    session.refresh(job)
    return job


def ensure_job_unique_index(engine: Engine) -> None:
    """Add the job.title_key column if missing and enforce one title per tenant.

    Existing rows are backfilled with their normalized title. If duplicates are
    found, a clear warning is logged pointing at scripts/dedupe_jobs.py and the
    unique index is skipped instead of crashing the app at startup.
    """
    try:
        inspector = inspect(engine)
        if "job" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("job")}

        with engine.begin() as connection:
            if "title_key" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE job ADD COLUMN title_key VARCHAR NOT NULL DEFAULT ''"
                    )
                )

            rows = connection.execute(text("SELECT id, title FROM job")).fetchall()
            for row_id, title in rows:
                connection.execute(
                    text("UPDATE job SET title_key = :key WHERE id = :id"),
                    {"key": normalize_title(title or ""), "id": row_id},
                )

            duplicates = connection.execute(
                text(
                    "SELECT tenant_id, title_key, COUNT(*) AS n FROM job "
                    "GROUP BY tenant_id, title_key HAVING COUNT(*) > 1"
                )
            ).fetchall()
            if duplicates:
                logger.warning(
                    "Found %d duplicate job title group(s); skipping the unique "
                    "index on (tenant_id, title_key). Run "
                    "`python -m scripts.dedupe_jobs --apply` to merge duplicates, "
                    "then restart the API.",
                    len(duplicates),
                )
                return

            connection.execute(
                text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {JOB_TITLE_INDEX_NAME} "
                    "ON job (tenant_id, title_key)"
                )
            )
    except Exception:  # pragma: no cover - defensive: never block startup
        logger.exception("Could not ensure the unique job title index")


def list_jobs(session: Session, tenant_id: int) -> list[Job]:
    """List all jobs belonging to the current tenant."""
    statement = (
        select(Job)
        .where(Job.tenant_id == tenant_id)
        .order_by(Job.created_at.desc())
    )
    return list(session.exec(statement).all())


def candidate_counts_by_job(session: Session, tenant_id: int) -> dict[int, int]:
    """Map job id to its number of applications for the tenant, in one query."""
    statement = (
        select(Application.job_id, func.count(Application.id))
        .where(Application.tenant_id == tenant_id)
        .group_by(Application.job_id)
    )
    return {
        int(job_id): int(count)
        for job_id, count in session.exec(statement).all()
    }


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
    """Return every non-withdrawn application for the job, best score first.

    The comparison covers the whole pipeline for the tenant's job, including
    rejected and not-yet-analyzed applications. Unscored applications are always
    listed last so a null score never sorts ahead of a real one.
    """
    job = get_job(session=session, job_id=job_id, tenant_id=tenant_id)

    statement = (
        select(Application, Candidate.full_name)
        .join(Candidate, Application.candidate_id == Candidate.id)
        .where(
            Application.tenant_id == tenant_id,
            Application.job_id == job_id,
            Candidate.tenant_id == tenant_id,
            Application.status != "withdrawn",
        )
        .order_by(Application.id)
    )
    rows = session.exec(statement).all()

    # A NULL score must always sort last; do it in Python so the ordering does
    # not depend on the database's NULL semantics.
    rows = sorted(rows, key=lambda row: (row[0].score is None, -(row[0].score or 0.0)))

    candidates: list[CompareCandidateRead] = []
    for application, full_name in rows:
        # Unanalyzed applications still appear, with a null score and no detail.
        bundle = application.analysis or {}
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
                score=application.score,
                recommendation=analysis.get("recommendation", ""),
                confidence=analysis.get("confidence", ""),
                years=(analysis.get("candidate") or {}).get("total_years_experience"),
                breakdown=breakdown,
                criteria=criteria,
                flags=bundle.get("flags", []),
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
        counts=CompareCountsRead(
            total=len(candidates),
            scored=sum(1 for candidate in candidates if candidate.score is not None),
        ),
    )
