from datetime import datetime, timezone
from typing import Any
from sqlmodel import Session, select

from app.exceptions import (
    ApprovalRequiredException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.models import (
    Application,
    Approval,
    ApprovalActionType,
    ApprovalStatus,
    AuditActorType,
    Candidate,
    Job,
    User,
    UserRole,
)
from app.schemas.approval import ApprovalRead
from app.services.audit_service import log_event


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


def resolve_target_labels(
    session: Session,
    tenant_id: int,
    target_type: str,
    target_id: int,
) -> tuple[str | None, str | None]:
    """Resolve (candidate_name, job_title) for an application-backed approval.

    Approvals point at a target by type/id. Only "application" targets map to a
    candidate and job; any other type, or a target that no longer exists, yields
    (None, None) so listing approvals never fails on stale data.
    """
    if target_type != "application":
        return None, None
    statement = (
        select(Candidate.full_name, Job.title)
        .join(Application, Application.candidate_id == Candidate.id)
        .join(Job, Application.job_id == Job.id)
        .where(
            Application.id == target_id,
            Application.tenant_id == tenant_id,
        )
    )
    row = session.exec(statement).first()
    if not row:
        return None, None
    candidate_name, job_title = row
    return candidate_name, job_title


def build_approval_read(
    session: Session,
    tenant_id: int,
    approval: Approval,
) -> ApprovalRead:
    """Serialize an approval, adding the candidate name and job title it targets."""
    candidate_name, job_title = resolve_target_labels(
        session=session,
        tenant_id=tenant_id,
        target_type=approval.target_type,
        target_id=approval.target_id,
    )
    read = ApprovalRead.model_validate(approval)
    return read.model_copy(
        update={"candidate_name": candidate_name, "job_title": job_title}
    )
