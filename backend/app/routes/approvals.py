from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas.approval import ApprovalDecisionRequest, ApprovalRead
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalRead])
def get_approvals(
    status: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ApprovalRead]:
    """List tenant approvals, optionally filtered by status (e.g. ?status=pending)."""
    approvals = approval_service.list_approvals(
        session=session,
        tenant_id=current_user.tenant_id,
        status=status,
    )
    return [ApprovalRead.model_validate(a) for a in approvals]


@router.get("/{id}", response_model=ApprovalRead)
def get_approval(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApprovalRead:
    """Retrieve an approval by ID scoped to current user's tenant."""
    approval = approval_service.get_approval(
        session=session,
        approval_id=id,
        tenant_id=current_user.tenant_id,
    )
    return ApprovalRead.model_validate(approval)


@router.post("/{id}/approve", response_model=ApprovalRead)
def approve_approval(
    id: int,
    decision: ApprovalDecisionRequest | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApprovalRead:
    """Approve a pending approval (admin or approver only)."""
    note = decision.note if decision else None
    approval = approval_service.approve(
        session=session,
        approval_id=id,
        user=current_user,
        note=note,
    )
    return ApprovalRead.model_validate(approval)


@router.post("/{id}/reject", response_model=ApprovalRead)
def reject_approval(
    id: int,
    decision: ApprovalDecisionRequest | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApprovalRead:
    """Reject a pending approval (admin or approver only)."""
    note = decision.note if decision else None
    approval = approval_service.reject(
        session=session,
        approval_id=id,
        user=current_user,
        note=note,
    )
    return ApprovalRead.model_validate(approval)
