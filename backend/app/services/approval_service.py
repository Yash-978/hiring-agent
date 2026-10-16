from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func
from sqlmodel import Session, select

from app.exceptions import (
    ApprovalRequiredException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
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
    User,
    UserRole,
)
from app.schemas.approval import ApprovalRead
from app.services.audit_service import log_event


# Which application stage a decision moves the target application to.
_DECISION_APPLICATION_STATUS: dict[tuple[str, str], str] = {
    (
        ApprovalActionType.SHORTLIST.value,
        ApprovalStatus.APPROVED.value,
    ): ApplicationStatus.SHORTLIST_APPROVED.value,
    (
        ApprovalActionType.SHORTLIST.value,
        ApprovalStatus.REJECTED.value,
    ): ApplicationStatus.SHORTLIST_REJECTED.value,
    (
        ApprovalActionType.OFFER_LETTER.value,
        ApprovalStatus.APPROVED.value,
    ): ApplicationStatus.OFFER_APPROVED.value,
    (
        ApprovalActionType.OFFER_LETTER.value,
        ApprovalStatus.REJECTED.value,
    ): ApplicationStatus.OFFER_REJECTED.value,
}


def request_approval(
    session: Session,
    tenant_id: int,
    action_type: ApprovalActionType | str,
    target_type: str,
    target_id: int,
    payload: dict[str, Any] | None,
    requested_by: int,
) -> Approval:
    """Create a pending approval and record an audit log entry."""
    action_val = (
        action_type.value
        if isinstance(action_type, ApprovalActionType)
        else str(action_type)
    )

    approval = Approval(
        tenant_id=tenant_id,
        action_type=action_val,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        status=ApprovalStatus.PENDING.value,
        requested_by=requested_by,
    )
    session.add(approval)
    session.flush()

    assert approval.id is not None
    # Lookup requester email for clear audit logging if user exists
    user = session.get(User, requested_by)
    requester_name = user.email if user else f"user_{requested_by}"

    log_event(
        session=session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=requester_name,
        action="request_approval",
        entity_type="approval",
        entity_id=approval.id,
        details={
            "action_type": action_val,
            "target_type": target_type,
            "target_id": target_id,
        },
    )

    session.commit()
    session.refresh(approval)
    return approval


def _find_target_application(
    session: Session,
    tenant_id: int,
    approval: Approval,
) -> Application | None:
    """Resolve the application an approval is about, scoped to the tenant."""
    if approval.target_type == "application":
        application = session.get(Application, approval.target_id)
    elif approval.target_type == "letter":
        letter = session.get(Letter, approval.target_id)
        if not letter or letter.tenant_id != tenant_id:
            return None
        application = session.get(Application, letter.application_id)
    else:
        return None

    if not application or application.tenant_id != tenant_id:
        return None
    return application


def _apply_decision_to_application(
    session: Session,
    tenant_id: int,
    approval: Approval,
    decision_status: str,
) -> Application | None:
    """Move the target application to the stage implied by the decision.

    Returns the updated application, or None when the approval does not point at
    a resolvable application for this tenant. Never raises on stale targets.
    """
    action_value = (
        approval.action_type.value
        if isinstance(approval.action_type, ApprovalActionType)
        else str(approval.action_type)
    )
    new_status = _DECISION_APPLICATION_STATUS.get((action_value, decision_status))
    if not new_status:
        return None

    application = _find_target_application(session, tenant_id, approval)
    if not application:
        return None

    application.status = new_status
    session.add(application)
    return application


def approve(
    session: Session,
    approval_id: int,
    user: User,
    note: str | None = None,
) -> Approval:
    """Approve a pending approval, verifying tenant, role, and pending status."""
    approval = session.get(Approval, approval_id)
    if not approval or approval.tenant_id != user.tenant_id:
        raise NotFoundException(f"Approval {approval_id} not found")

    user_role = (
        user.role.value if isinstance(user.role, UserRole) else str(user.role)
    )
    if user_role not in (UserRole.ADMIN.value, UserRole.APPROVER.value):
        raise ForbiddenException("Only admin or approver may decide approvals")

    curr_status = (
        approval.status.value
        if isinstance(approval.status, ApprovalStatus)
        else str(approval.status)
    )
    if curr_status != ApprovalStatus.PENDING.value:
        raise ConflictException("Approval is already decided")

    approval.status = ApprovalStatus.APPROVED.value
    approval.decided_by_user_id = user.id
    approval.decided_at = datetime.now(timezone.utc)
    approval.decision_note = note

    session.add(approval)
    session.flush()

    application = _apply_decision_to_application(
        session=session,
        tenant_id=user.tenant_id,
        approval=approval,
        decision_status=ApprovalStatus.APPROVED.value,
    )

    log_event(
        session=session,
        tenant_id=user.tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=user.email,
        action="approve",
        entity_type="approval",
        entity_id=approval.id,
        details={
            "action_type": approval.action_type,
            "decision_note": note,
            "application_id": application.id if application else None,
            "application_status": application.status if application else None,
        },
    )

    session.commit()
    session.refresh(approval)
    return approval


def reject(
    session: Session,
    approval_id: int,
    user: User,
    note: str | None = None,
) -> Approval:
    """Reject a pending approval, verifying tenant, role, and pending status."""
    approval = session.get(Approval, approval_id)
    if not approval or approval.tenant_id != user.tenant_id:
        raise NotFoundException(f"Approval {approval_id} not found")

    user_role = (
        user.role.value if isinstance(user.role, UserRole) else str(user.role)
    )
    if user_role not in (UserRole.ADMIN.value, UserRole.APPROVER.value):
        raise ForbiddenException("Only admin or approver may decide approvals")

    curr_status = (
        approval.status.value
        if isinstance(approval.status, ApprovalStatus)
        else str(approval.status)
    )
    if curr_status != ApprovalStatus.PENDING.value:
        raise ConflictException("Approval is already decided")

    approval.status = ApprovalStatus.REJECTED.value
    approval.decided_by_user_id = user.id
    approval.decided_at = datetime.now(timezone.utc)
    approval.decision_note = note

    session.add(approval)
    session.flush()

    application = _apply_decision_to_application(
        session=session,
        tenant_id=user.tenant_id,
        approval=approval,
        decision_status=ApprovalStatus.REJECTED.value,
    )

    log_event(
        session=session,
        tenant_id=user.tenant_id,
        actor_type=AuditActorType.USER,
        actor_name=user.email,
        action="reject",
        entity_type="approval",
        entity_id=approval.id,
        details={
            "action_type": approval.action_type,
            "decision_note": note,
            "application_id": application.id if application else None,
            "application_status": application.status if application else None,
        },
    )

    session.commit()
    session.refresh(approval)
    return approval


def require_approved(
    session: Session,
    approval_id: int,
    tenant_id: int,
    expected_action_type: ApprovalActionType | str,
) -> Approval:
    """Verify approval is approved and matches tenant and expected action type.
    
    This is the ONLY gate any outgoing action may use.
    """
    approval = session.get(Approval, approval_id)
    if not approval:
        raise ApprovalRequiredException(f"Approval {approval_id} does not exist")

    if approval.tenant_id != tenant_id:
        raise ApprovalRequiredException("Approval tenant mismatch")

    exp_action = (
        expected_action_type.value
        if isinstance(expected_action_type, ApprovalActionType)
        else str(expected_action_type)
    )
    act_action = (
        approval.action_type.value
        if isinstance(approval.action_type, ApprovalActionType)
        else str(approval.action_type)
    )
    if act_action != exp_action:
        raise ApprovalRequiredException(
            f"Approval action mismatch: expected '{exp_action}', got '{act_action}'"
        )

    curr_status = (
        approval.status.value
        if isinstance(approval.status, ApprovalStatus)
        else str(approval.status)
    )
    if curr_status != ApprovalStatus.APPROVED.value:
        raise ApprovalRequiredException(
            f"Approval {approval_id} is not approved (current status: '{curr_status}')"
        )

    return approval


def list_approvals(
    session: Session,
    tenant_id: int,
    status: str | ApprovalStatus | None = None,
) -> list[Approval]:
    """List approvals belonging to a tenant, optionally filtered by status."""
    query = select(Approval).where(Approval.tenant_id == tenant_id)
    if status:
        st_val = status.value if isinstance(status, ApprovalStatus) else str(status)
        query = query.where(Approval.status == st_val)
    query = query.order_by(Approval.created_at.desc())
    return list(session.exec(query).all())


def get_approval(
    session: Session,
    approval_id: int,
    tenant_id: int,
) -> Approval:
    """Get single approval verifying it belongs to the tenant."""
    approval = session.get(Approval, approval_id)
    if not approval or approval.tenant_id != tenant_id:
        raise NotFoundException(f"Approval {approval_id} not found")
    return approval


def count_approvals_by_status(
    session: Session,
    tenant_id: int,
) -> dict[str, int]:
    """Count a tenant's approvals per status in a single grouped query."""
    rows = session.exec(
        select(Approval.status, func.count())
        .where(Approval.tenant_id == tenant_id)
        .group_by(Approval.status)
    ).all()

    counts = {status.value: 0 for status in ApprovalStatus}
    for status_value, total in rows:
        key = (
            status_value.value
            if isinstance(status_value, ApprovalStatus)
            else str(status_value)
        )
        counts[key] = int(total)
    return counts


def _resolve_application_details(
    session: Session,
    tenant_id: int,
    application_ids: set[int],
) -> dict[int, dict[str, Any]]:
    """Batch-resolve candidate name, job title, score and recommendation.

    One query for every application id, so listing approvals never issues a
    query per row.
    """
    if not application_ids:
        return {}

    statement = (
        select(
            Application.id,
            Candidate.full_name,
            Job.title,
            Application.score,
            Application.analysis,
        )
        .join(Candidate, Application.candidate_id == Candidate.id)
        .join(Job, Application.job_id == Job.id)
        .where(
            Application.tenant_id == tenant_id,
            Application.id.in_(application_ids),
        )
    )

    details: dict[int, dict[str, Any]] = {}
    for app_id, candidate_name, job_title, score, analysis in session.exec(
        statement
    ).all():
        recommendation: str | None = None
        if isinstance(analysis, dict):
            inner = analysis.get("analysis")
            if isinstance(inner, dict):
                recommendation = inner.get("recommendation")
        details[app_id] = {
            "application_id": app_id,
            "candidate_name": candidate_name,
            "job_title": job_title,
            "score": score,
            "recommendation": recommendation,
        }
    return details


def build_approval_reads(
    session: Session,
    tenant_id: int,
    approvals: Sequence[Approval],
) -> list[ApprovalRead]:
    """Serialize approvals, batch-resolving names, scores and recommendations.

    Approvals point at a target by type/id. "application" targets map directly
    to an application; "letter" targets resolve through the letter's
    application_id. Any stale or foreign target yields nulls so listing never
    fails on old data. All lookups are batched to avoid N+1 queries.
    """
    items = list(approvals)
    if not items:
        return []

    letter_ids = [a.target_id for a in items if a.target_type == "letter"]
    letter_to_application: dict[int, int] = {}
    if letter_ids:
        letter_rows = session.exec(
            select(Letter.id, Letter.application_id).where(
                Letter.tenant_id == tenant_id,
                Letter.id.in_(letter_ids),
            )
        ).all()
        letter_to_application = {row[0]: row[1] for row in letter_rows}

    target_application: dict[int, int] = {}
    for index, approval in enumerate(items):
        if approval.target_type == "application":
            target_application[index] = approval.target_id
        elif approval.target_type == "letter":
            application_id = letter_to_application.get(approval.target_id)
            if application_id is not None:
                target_application[index] = application_id

    details = _resolve_application_details(
        session=session,
        tenant_id=tenant_id,
        application_ids=set(target_application.values()),
    )

    requester_ids = {a.requested_by for a in items}
    requester_names: dict[int, str] = {}
    if requester_ids:
        user_rows = session.exec(
            select(User.id, User.email).where(User.id.in_(requester_ids))
        ).all()
        requester_names = {row[0]: row[1] for row in user_rows}

    reads: list[ApprovalRead] = []
    for index, approval in enumerate(items):
        candidate_application_id = target_application.get(index)
        detail = (
            details.get(candidate_application_id)
            if candidate_application_id is not None
            else None
        )
        read = ApprovalRead.model_validate(approval)
        reads.append(
            read.model_copy(
                update={
                    "application_id": detail["application_id"] if detail else None,
                    "candidate_name": detail["candidate_name"] if detail else None,
                    "job_title": detail["job_title"] if detail else None,
                    "score": detail["score"] if detail else None,
                    "recommendation": (
                        detail["recommendation"] if detail else None
                    ),
                    "requested_by_name": requester_names.get(approval.requested_by),
                }
            )
        )
    return reads


def build_approval_read(
    session: Session,
    tenant_id: int,
    approval: Approval,
) -> ApprovalRead:
    """Serialize a single approval with its resolved labels and score."""
    return build_approval_reads(
        session=session,
        tenant_id=tenant_id,
        approvals=[approval],
    )[0]
