from datetime import date
import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pypdf import PdfReader
from sqlmodel import Session

from app.db import get_session
from app.deps import get_current_user
from app.exceptions import NotFoundException
from app.models import AuditActorType, User
from app.schemas.application import (
    ApplicationAnalysisRead,
    ApplicationCreate,
    ApplicationRead,
    AuditLogRead,
)
from app.schemas.letter import OfferDraftRequest
from app.services import application_service, audit_service
from app.services.audit_service import log_event

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationRead, status_code=201)
def create_application(
    data: ApplicationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApplicationRead:
    """Create a new application from candidate_id and job_id."""
    app, candidate_name, job_title = application_service.create_application(
        session=session,
        tenant_id=current_user.tenant_id,
        candidate_id=data.candidate_id,
        job_id=data.job_id,
        creator_name=current_user.email,
    )
    assert app.id is not None
    status_val = app.status.value if hasattr(app.status, "value") else str(app.status)
    return ApplicationRead(
        id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        candidate_name=candidate_name,
        job_title=job_title,
        status=status_val,
        score=app.score,
        score_reasoning=app.score_reasoning,
        created_at=app.created_at,
    )


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ApplicationRead]:
    """List applications for current user's tenant with candidate and job names."""
    rows = application_service.list_applications_with_details(
        session=session,
        tenant_id=current_user.tenant_id,
    )
    result: list[ApplicationRead] = []
    for app, candidate_name, job_title in rows:
        assert app.id is not None
        status_val = app.status.value if hasattr(app.status, "value") else str(app.status)
        result.append(
            ApplicationRead(
                id=app.id,
                candidate_id=app.candidate_id,
                job_id=app.job_id,
                candidate_name=candidate_name,
                job_title=job_title,
                status=status_val,
                score=app.score,
                score_reasoning=app.score_reasoning,
                created_at=app.created_at,
            )
        )
    return result


@router.get("/{id}", response_model=ApplicationRead)
def get_application(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApplicationRead:
    """Get single application by ID with candidate and job names."""
    app, candidate_name, job_title = application_service.get_application_with_details(
        session=session,
        application_id=id,
        tenant_id=current_user.tenant_id,
    )
    assert app.id is not None
    status_val = app.status.value if hasattr(app.status, "value") else str(app.status)
    return ApplicationRead(
        id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        candidate_name=candidate_name,
        job_title=job_title,
        status=status_val,
        score=app.score,
        score_reasoning=app.score_reasoning,
        created_at=app.created_at,
    )


MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}


@router.post("/{id}/analyze", response_model=ApplicationRead)
async def analyze_application(
    id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApplicationRead:
    """Analyze application resume and create shortlist approval."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and TXT files are allowed",
        )

    content = await file.read()
    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 5 MB limit",
        )

    # Verify the application exists and belongs to the caller's tenant before
    # doing any parsing or LLM work. Cross-tenant callers get a 404.
    try:
        application_service.get_application_with_details(
            session=session,
            application_id=id,
            tenant_id=current_user.tenant_id,
        )
    except NotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {id} not found",
        )

    if file.content_type == "application/pdf":
        try:
            pdf_reader = PdfReader(io.BytesIO(content))
            resume_text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse PDF: {e}",
            )
    else:
        resume_text = content.decode("utf-8", errors="replace")

    if len(resume_text.strip()) < application_service.MIN_RESUME_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Resume text is too short to analyze "
                f"(minimum {application_service.MIN_RESUME_CHARS} characters)"
            ),
        )

    try:
        app, candidate, job, _ = application_service.analyze_application(
            session=session,
            tenant_id=current_user.tenant_id,
            application_id=id,
            resume_text=resume_text,
            user_id=current_user.id,
            resume_bytes=content,
            resume_content_type=file.content_type,
        )
    except NotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {id} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Analysis failed: {e}",
        )

    assert app.id is not None
    status_val = app.status.value if hasattr(app.status, "value") else str(app.status)
    return ApplicationRead(
        id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        candidate_name=candidate.full_name if candidate else "",
        job_title=job.title if job else "",
        status=status_val,
        score=app.score,
        score_reasoning=app.score_reasoning,
        created_at=app.created_at,
    )


@router.get("/{id}/analysis", response_model=ApplicationAnalysisRead)
def get_application_analysis(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApplicationAnalysisRead:
    """Return the stored resume analysis for an application (tenant-scoped)."""
    try:
        return application_service.build_analysis_read(
            session=session,
            application_id=id,
            tenant_id=current_user.tenant_id,
        )
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{id}/resume")
def download_application_resume(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download the stored resume upload for an application (tenant-scoped)."""
    try:
        file_path, media_type = application_service.resolve_resume_path(
            session=session,
            application_id=id,
            tenant_id=current_user.tenant_id,
        )
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    log_event(
        session=session,
        tenant_id=current_user.tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=current_user.email,
        action="resume_downloaded",
        entity_type="application",
        entity_id=id,
        details={},
    )
    session.commit()

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"resume_{id}{file_path.suffix}",
    )


@router.post("/{id}/offer-draft", response_model=ApplicationRead)
def create_offer_draft(
    id: int,
    data: OfferDraftRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApplicationRead:
    """Create offer draft for an application with approved shortlist."""
    try:
        app, candidate, job, _, _ = application_service.create_offer_draft(
            session=session,
            tenant_id=current_user.tenant_id,
            application_id=id,
            salary=data.salary,
            currency=data.currency,
            start_date=data.start_date.isoformat(),
            user_id=current_user.id,
        )
    except NotFoundException as e:
        if "Shortlist approval not found or not approved" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Shortlist approval required and must be approved",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Offer draft failed: {e}",
        )

    assert app.id is not None
    status_val = app.status.value if hasattr(app.status, "value") else str(app.status)
    return ApplicationRead(
        id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        candidate_name=candidate.full_name if candidate else "",
        job_title=job.title if job else "",
        status=status_val,
        score=app.score,
        score_reasoning=app.score_reasoning,
        created_at=app.created_at,
    )


@router.get("/{id}/audit", response_model=list[AuditLogRead])
def get_application_audit(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[AuditLogRead]:
    """Get audit log events for a specific application (tenant-filtered, newest last)."""
    # Verify application exists and belongs to tenant
    application_service.get_application_with_details(
        session=session,
        application_id=id,
        tenant_id=current_user.tenant_id,
    )
    # Return audit logs for this application
    return audit_service.get_audit_logs_for_entity(
        session=session,
        tenant_id=current_user.tenant_id,
        entity_type="application",
        entity_id=id,
    )
