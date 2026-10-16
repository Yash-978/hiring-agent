from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas.job import JobCompareRead, JobCreate, JobRead
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead, status_code=201)
def create_job(
    data: JobCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Create a new job posting for current user's tenant."""
    job = job_service.create_job(
        session=session,
        tenant_id=current_user.tenant_id,
        title=data.title,
        description=data.description,
        status=data.status,
        must_have_skills=data.must_have_skills,
        nice_to_have_skills=data.nice_to_have_skills,
        min_years_experience=data.min_years_experience,
        creator_name=current_user.email,
    )
    return JobRead.model_validate(job)


@router.get("", response_model=list[JobRead])
def list_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[JobRead]:
    """List all jobs for current user's tenant."""
    jobs = job_service.list_jobs(
        session=session,
        tenant_id=current_user.tenant_id,
    )
    return [JobRead.model_validate(j) for j in jobs]


@router.get("/{id}", response_model=JobRead)
def get_job(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Get single job by ID scoped to current user's tenant."""
    job = job_service.get_job(
        session=session,
        job_id=id,
        tenant_id=current_user.tenant_id,
    )
    return JobRead.model_validate(job)


@router.get("/{id}/compare", response_model=JobCompareRead)
def compare_job_candidates(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobCompareRead:
    """Compare analyzed candidates for a job, best score first (tenant-scoped)."""
    return job_service.compare_job_candidates(
        session=session,
        tenant_id=current_user.tenant_id,
        job_id=id,
    )
