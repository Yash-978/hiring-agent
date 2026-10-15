from sqlmodel import Session, select

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
from app.agents import (
    analyze_resume,
    draft_offer,
    get_llm_client,
    LLMError,
    OfferDraft,
    ResumeAnalysis,
)


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


def analyze_application(
    session: Session,
    tenant_id: int,
    application_id: int,
    resume_text: str,
    user_id: int,
) -> tuple[Application, Candidate, Job, ResumeAnalysis]:
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
    if candidate:
        candidate.resume_text = resume_text
        session.add(candidate)

    client = get_llm_client()
    try:
        analysis = analyze_resume(client, resume_text, job.description)
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

    # Update application with score and reasoning
    application.status = ApplicationStatus.ANALYZED.value
    application.score = float(analysis.score)
    application.score_reasoning = analysis.reasoning
    session.add(application)

    # Create pending shortlist approval
    approval = request_approval(
        session=session,
        tenant_id=tenant_id,
        action_type=ApprovalActionType.SHORTLIST,
        target_type="application",
        target_id=application.id,
        payload=analysis.model_dump(),
        requested_by=user_id,
    )

    # Log audit for agent analysis
    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.AGENT,
        actor_name="resume_agent",
        action="analyze_resume",
        entity_type="application",
        entity_id=application.id,
        details={
            "score": analysis.score,
            "skills": analysis.skills,
            "years_experience": analysis.years_experience,
            "approval_id": approval.id,
        },
    )

    session.commit()
    session.refresh(application)
    session.refresh(candidate)
    session.refresh(job)
    return application, candidate, job, analysis


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
