from pathlib import Path
import hashlib

from sqlmodel import Session, select

from app.config import get_settings
from app.exceptions import NotFoundException
from app.models import (
    Application,
    ApplicationStatus,
    Approval,
    ApprovalActionType,
    ApprovalStatus,
    AuditActorType,
    Candidate,
    Job,
    Letter,
    Tenant,
)
from app.services.approval_service import require_approved, request_approval
from app.services.audit_service import log_event
from app.schemas.application import (
    AnalysisCandidateRead,
    AnalysisCriterionRead,
    AnalysisJobRef,
    ApplicationAnalysisRead,
)
from app.agents import (
    analyze_resume,
    draft_offer,
    extract_job_requirements,
    get_llm_client,
    LLMError,
    OfferDraft,
    ResumeAnalysisResult,
)

MIN_RESUME_CHARS = 200

# Server-chosen extensions keyed by the content types we accept. The client's
# filename is never trusted; the stored name is always "resume.<ext>".
_RESUME_EXTENSIONS = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

# Media types served back for the extensions we may store.
_RESUME_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _resume_extension(content_type: str | None) -> str:
    """Return a safe file extension for the given content type."""
    normalized = (content_type or "").split(";")[0].strip().lower()
    return _RESUME_EXTENSIONS.get(normalized, "bin")


def _save_resume(
    tenant_id: int,
    application_id: int,
    content: bytes,
    content_type: str | None,
) -> str:
    """Save the original upload under STORAGE_DIR and return its relative path.

    The path is tenant-scoped and uses a server-made filename, so a crafted
    client filename can never escape the storage root.
    """
    storage_root = get_settings().STORAGE_DIR
    target_dir = (
        storage_root / "tenants" / str(tenant_id) / "applications" / str(application_id)
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"resume.{_resume_extension(content_type)}"
    file_path.write_bytes(content)
    # Store a portable POSIX-style relative path (forward slashes on every OS).
    return file_path.relative_to(storage_root).as_posix()


def create_application(
    session: Session,
    tenant_id: int,
    candidate_id: int,
    job_id: int,
    creator_name: str = "",
) -> tuple[Application, str, str]:
    """Create a new application verifying candidate and job belong to the tenant."""
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.tenant_id != tenant_id:
        raise NotFoundException(f"Candidate {candidate_id} not found")

    job = session.get(Job, job_id)
    if not job or job.tenant_id != tenant_id:
        raise NotFoundException(f"Job {job_id} not found")

    application = Application(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        job_id=job_id,
        status=ApplicationStatus.NEW.value,
    )
    session.add(application)
    session.flush()

    assert application.id is not None
    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=creator_name or "system",
        action="create_application",
        entity_type="application",
        entity_id=application.id,
        details={"candidate_id": candidate_id, "job_id": job_id},
    )

    session.commit()
    session.refresh(application)
    return application, candidate.full_name, job.title


def list_applications_with_details(
    session: Session,
    tenant_id: int,
) -> list[tuple[Application, str, str]]:
    """List applications for tenant joined with candidate name and job title."""
    statement = (
        select(Application, Candidate.full_name, Job.title)
        .join(Candidate, Application.candidate_id == Candidate.id)
        .join(Job, Application.job_id == Job.id)
        .where(
            Application.tenant_id == tenant_id,
            Candidate.tenant_id == tenant_id,
            Job.tenant_id == tenant_id,
        )
        .order_by(Application.created_at.desc())
    )
    return list(session.exec(statement).all())


def get_application_with_details(
    session: Session,
    application_id: int,
    tenant_id: int,
) -> tuple[Application, str, str]:
    """Retrieve an application with candidate name and job title, raising NotFoundException otherwise."""
    statement = (
        select(Application, Candidate.full_name, Job.title)
        .join(Candidate, Application.candidate_id == Candidate.id)
        .join(Job, Application.job_id == Job.id)
        .where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
            Candidate.tenant_id == tenant_id,
            Job.tenant_id == tenant_id,
        )
    )
    result = session.exec(statement).first()
    if not result:
        raise NotFoundException(f"Application {application_id} not found")
    return result


def build_analysis_read(
    session: Session,
    application_id: int,
    tenant_id: int,
) -> ApplicationAnalysisRead:
    """Flatten the stored analysis bundle into the public response shape.

    Raises NotFoundException when the application is not in the tenant or has
    not been analyzed yet.
    """
    application, _candidate_name, job_title = get_application_with_details(
        session=session,
        application_id=application_id,
        tenant_id=tenant_id,
    )

    bundle = application.analysis
    if not bundle:
        raise NotFoundException(f"Application {application_id} has not been analyzed")

    analysis = bundle.get("analysis", {})
    return ApplicationAnalysisRead(
        application_id=application_id,
        job=AnalysisJobRef(id=application.job_id, title=job_title),
        candidate=AnalysisCandidateRead(**analysis.get("candidate", {})),
        criteria=[
            AnalysisCriterionRead(**criterion)
            for criterion in analysis.get("criteria", [])
        ],
        score=bundle.get("score"),
        breakdown=bundle.get("breakdown", {}),
        strengths=analysis.get("strengths", []),
        concerns=analysis.get("concerns", []),
        questions_for_candidate=analysis.get("questions_for_candidate", []),
        recommendation=analysis.get("recommendation", ""),
        confidence=analysis.get("confidence", ""),
        flags=bundle.get("flags", []),
        model=bundle.get("model", ""),
        prompt_version=bundle.get("prompt_version", ""),
        resume_available=bool(application.resume_path),
    )


def resolve_resume_path(
    session: Session,
    application_id: int,
    tenant_id: int,
) -> tuple[Path, str]:
    """Return the absolute stored resume path and its media type.

    Raises NotFoundException when the application is not in the tenant, no
    upload is stored, or the stored path escapes the storage root.
    """
    application, _candidate_name, _job_title = get_application_with_details(
        session=session,
        application_id=application_id,
        tenant_id=tenant_id,
    )
    if not application.resume_path:
        raise NotFoundException("Resume not available for this application")

    storage_root = get_settings().STORAGE_DIR.resolve()
    file_path = (storage_root / application.resume_path).resolve()
    if not file_path.is_relative_to(storage_root) or not file_path.is_file():
        raise NotFoundException("Resume not available for this application")

    media_type = _RESUME_MEDIA_TYPES.get(
        file_path.suffix.lower(), "application/octet-stream"
    )
    return file_path, media_type


def analyze_application(
    session: Session,
    tenant_id: int,
    application_id: int,
    resume_text: str,
    user_id: int,
    resume_bytes: bytes = b"",
    resume_content_type: str | None = None,
) -> tuple[Application, Candidate, Job, ResumeAnalysisResult]:
    """Analyze application resume, create approval, and log audit entries."""
    application, candidate_name, job_title = get_application_with_details(
        session=session,
        application_id=application_id,
        tenant_id=tenant_id,
    )

    # Get job for description
    job = session.get(Job, application.job_id)
    if not job:
        raise NotFoundException(f"Job {application.job_id} not found")

    # Store resume text on candidate
    candidate = session.get(Candidate, application.candidate_id)
    if not candidate:
        raise NotFoundException(f"Candidate {application.candidate_id} not found")
    candidate.resume_text = resume_text
    session.add(candidate)

    client = get_llm_client()

    # Extract structured requirements from the job description when the job
    # was created without them. On failure, log and leave the job empty.
    if (
        not job.must_have_skills
        and not job.nice_to_have_skills
        and job.min_years_experience is None
    ):
        try:
            requirements = extract_job_requirements(client, job.description)
        except LLMError:
            log_event(
                session=session,
                tenant_id=tenant_id,
                actor_type=AuditActorType.AGENT,
                actor_name="job_agent",
                action="job_extraction_failed",
                entity_type="job",
                entity_id=job.id,
                details={},
            )
        else:
            job.must_have_skills = requirements.must_have_skills
            job.nice_to_have_skills = requirements.nice_to_have_skills
            job.min_years_experience = requirements.min_years_experience
            session.add(job)

    try:
        result = analyze_resume(
            client=client,
            resume_text=resume_text,
            job_description=job.description,
            must_have_skills=job.must_have_skills,
            nice_to_have_skills=job.nice_to_have_skills,
            min_years_experience=job.min_years_experience,
            candidate_name=candidate.full_name,
            candidate_email=candidate.email,
        )
    except LLMError as e:
        log_event(
            session=session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.AGENT,
            actor_name="resume_agent",
            action="analysis_failed",
            entity_type="application",
            entity_id=application.id,
            details={"error": str(e)},
        )
        session.commit()
        raise

    analysis = result.analysis

    # Persist the original upload locally and store the full analysis bundle.
    application.resume_path = _save_resume(
        tenant_id=tenant_id,
        application_id=application.id,
        content=resume_bytes,
        content_type=resume_content_type,
    )
    application.analysis = result.model_dump()

    # Update application with the deterministic score and a short reasoning line
    application.status = ApplicationStatus.ANALYZED.value
    application.score = result.score
    application.score_reasoning = (
        f"{analysis.recommendation} (confidence: {analysis.confidence})"
    )
    session.add(application)

    # Create pending shortlist approval carrying the full analysis bundle
    request_approval(
        session=session,
        tenant_id=tenant_id,
        action_type=ApprovalActionType.SHORTLIST,
        target_type="application",
        target_id=application.id,
        payload=result.model_dump(),
        requested_by=user_id,
    )

    # Log audit for agent analysis (never log resume text or salaries)
    resume_sha8 = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()[:8]
    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.AGENT,
        actor_name="resume_agent",
        action="analysis_completed",
        entity_type="application",
        entity_id=application.id,
        details={
            "score": result.score,
            "model": result.model,
            "criteria_count": len(analysis.criteria),
            "resume_sha8": resume_sha8,
        },
    )

    session.commit()
    session.refresh(application)
    session.refresh(candidate)
    session.refresh(job)
    return application, candidate, job, result


def create_offer_draft(
    session: Session,
    tenant_id: int,
    application_id: int,
    salary: float,
    currency: str,
    start_date: str,
    user_id: int,
) -> tuple[Application, Candidate, Job, OfferDraft, Approval]:
    """Create offer draft, verify shortlist approval, create letter and offer approval."""

    application, candidate_name, job_title = get_application_with_details(
        session=session,
        application_id=application_id,
        tenant_id=tenant_id,
    )

    candidate = session.get(Candidate, application.candidate_id)
    if not candidate:
        raise NotFoundException(f"Candidate {application.candidate_id} not found")

    job = session.get(Job, application.job_id)
    if not job:
        raise NotFoundException(f"Job {application.job_id} not found")

    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise NotFoundException(f"Tenant {tenant_id} not found")

    # Verify shortlist approval is approved
    shortlist_approval = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_id,
            Approval.action_type == ApprovalActionType.SHORTLIST.value,
            Approval.target_type == "application",
            Approval.target_id == application_id,
            Approval.status == ApprovalStatus.APPROVED.value,
        )
    ).first()
    if not shortlist_approval:
        raise NotFoundException("Shortlist approval not found or not approved")

    # Verify using require_approved
    require_approved(
        session=session,
        approval_id=shortlist_approval.id,
        tenant_id=tenant_id,
        expected_action_type=ApprovalActionType.SHORTLIST,
    )

    # Draft offer letter
    client = get_llm_client()
    try:
        offer_draft = draft_offer(
            client=client,
            candidate_name=candidate.full_name,
            job_title=job.title,
            salary=salary,
            currency=currency,
            start_date=start_date,
            company_name=tenant.name,
        )
    except LLMError as e:
        log_event(
            session=session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.AGENT,
            actor_name="offer_agent",
            action="draft_failed",
            entity_type="application",
            entity_id=application.id,
            details={"error": str(e)},
        )
        session.commit()
        raise

    # Create letter record
    letter = Letter(
        tenant_id=tenant_id,
        application_id=application.id,
        approval_id=None,
        content=f"Subject: {offer_draft.subject}\n\n{offer_draft.body}",
    )
    session.add(letter)
    session.flush()

    # Create pending offer_letter approval
    offer_approval = request_approval(
        session=session,
        tenant_id=tenant_id,
        action_type=ApprovalActionType.OFFER_LETTER,
        target_type="letter",
        target_id=letter.id,
        payload={"salary": salary, "currency": currency, "start_date": start_date},
        requested_by=user_id,
    )

    # Update letter with offer approval id
    letter.approval_id = offer_approval.id
    session.add(letter)

    # Update application status
    application.status = ApplicationStatus.OFFER_DRAFTED.value
    session.add(application)

    # Log audit (never log salary per security rules)
    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.AGENT,
        actor_name="offer_agent",
        action="draft_offer",
        entity_type="letter",
        entity_id=letter.id,
        details={
            "application_id": application.id,
            "offer_approval_id": offer_approval.id,
            "currency": currency,
        },
    )

    session.commit()
    session.refresh(application)
    session.refresh(candidate)
    session.refresh(job)
    session.refresh(letter)
    return application, candidate, job, offer_draft, offer_approval
