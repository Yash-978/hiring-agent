"""Letters routes."""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.db import get_session
from app.deps import get_current_user
from app.exceptions import NotFoundException
from app.models import AuditActorType, Letter, User
from app.schemas.letter import LetterRead
from app.services import letter_service
from app.services.approval_service import require_approved
from app.services.audit_service import log_event

router = APIRouter(prefix="/letters", tags=["letters"])


@router.get("/{id}", response_model=LetterRead)
def get_letter(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LetterRead:
    """Retrieve a letter by ID scoped to current user's tenant."""
    letter = session.get(Letter, id)
    if not letter or letter.tenant_id != current_user.tenant_id:
        raise NotFoundException(f"Letter {id} not found")
    return LetterRead.model_validate(letter)


@router.post("/{id}/generate", response_model=LetterRead)
def generate_letter(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LetterRead:
    """Generate DOCX for letter if offer approval is approved."""
    letter = session.get(Letter, id)
    if not letter or letter.tenant_id != current_user.tenant_id:
        raise NotFoundException(f"Letter {id} not found")

    if letter.approval_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Letter has no associated offer approval",
        )

    # Verify offer_letter approval is approved
    try:
        require_approved(
            session=session,
            approval_id=letter.approval_id,
            tenant_id=letter.tenant_id,
            expected_action_type="offer_letter",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Offer approval not approved",
        )

    # Generate DOCX
    letter = letter_service.generate_docx(
        session=session,
        letter_id=id,
        tenant_id=current_user.tenant_id,
    )

    # Log audit
    log_event(
        session=session,
        tenant_id=current_user.tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=current_user.email,
        action="letter_generated",
        entity_type="letter",
        entity_id=letter.id,
        details={"file_path": letter.file_path},
    )
    session.commit()

    return LetterRead.model_validate(letter)


@router.get("/{id}/download")
def download_letter(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Download letter DOCX file if offer approval is approved."""
    letter = session.get(Letter, id)
    if not letter or letter.tenant_id != current_user.tenant_id:
        raise NotFoundException(f"Letter {id} not found")

    if letter.approval_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Letter has no associated offer approval",
        )

    # Verify offer_letter approval is approved
    try:
        require_approved(
            session=session,
            approval_id=letter.approval_id,
            tenant_id=letter.tenant_id,
            expected_action_type="offer_letter",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Offer approval not approved",
        )

    if not letter.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Letter file not generated yet",
        )

    # Build full path
    file_path = Path("backend") / letter.file_path
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Letter file not found on disk",
        )

    # Log audit
    log_event(
        session=session,
        tenant_id=current_user.tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=current_user.email,
        action="letter_downloaded",
        entity_type="letter",
        entity_id=letter.id,
        details={"file_path": letter.file_path},
    )
    session.commit()

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"offer_letter_{letter.id}.docx",
    )