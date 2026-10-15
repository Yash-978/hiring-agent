from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas.candidate import CandidateCreate, CandidateRead
from app.services import candidate_service

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateRead, status_code=201)
def create_candidate(
    data: CandidateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CandidateRead:
    """Create a new candidate profile for current user's tenant."""
    candidate = candidate_service.create_candidate(
        session=session,
        tenant_id=current_user.tenant_id,
        full_name=data.full_name,
        email=data.email,
        resume_text=data.resume_text,
        parsed_data=data.parsed_data,
        creator_name=current_user.email,
    )
    return CandidateRead.model_validate(candidate)


@router.get("", response_model=list[CandidateRead])
def list_candidates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CandidateRead]:
    """List all candidates for current user's tenant."""
    candidates = candidate_service.list_candidates(
        session=session,
        tenant_id=current_user.tenant_id,
    )
    return [CandidateRead.model_validate(c) for c in candidates]


@router.get("/{id}", response_model=CandidateRead)
def get_candidate(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CandidateRead:
    """Get single candidate by ID scoped to current user's tenant."""
    candidate = candidate_service.get_candidate(
        session=session,
        candidate_id=id,
        tenant_id=current_user.tenant_id,
    )
    return CandidateRead.model_validate(candidate)
