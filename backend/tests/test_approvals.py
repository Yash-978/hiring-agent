from typing import Any
# pyrefly: ignore [missing-import]
import pytest
from fastapi.testclient import TestClient
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select    

from app.exceptions import ApprovalRequiredException
from app.models import Approval, ApprovalActionType, ApprovalStatus, AuditLog, UserRole
from app.services import approval_service
from tests.conftest import create_tenant_user


def test_approve_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    user_a = tenant_a["user"]

    # Create pending approval
    approval = approval_service.request_approval(
        session=session,
        tenant_id=tenant_a["tenant"].id,
        action_type=ApprovalActionType.SHORTLIST,
        target_type="application",
        target_id=101,
        payload={"candidate_name": "John Doe", "score": 8.5},
        requested_by=user_a.id,
    )

    # Approve via API
    response = client.post(
        f"/approvals/{approval.id}/approve",
        headers=tenant_a["headers"],
        json={"note": "Looks like a great fit"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == approval.id
    assert data["status"] == "approved"
    assert data["decision_note"] == "Looks like a great fit"
    assert data["decided_by_user_id"] == user_a.id
    assert data["decided_at"] is not None

    # Verify audit row was created
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "approve",
            AuditLog.entity_id == approval.id,
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == user_a.email
    assert audit.details["decision_note"] == "Looks like a great fit"


def test_reject_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    user_a = tenant_a["user"]

    approval = approval_service.request_approval(
        session=session,
        tenant_id=tenant_a["tenant"].id,
        action_type=ApprovalActionType.OFFER_LETTER,
        target_type="application",
        target_id=102,
        payload={"salary": 120000},
        requested_by=user_a.id,
    )

    response = client.post(
        f"/approvals/{approval.id}/reject",
        headers=tenant_a["headers"],
        json={"note": "Salary too high"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["decision_note"] == "Salary too high"
    assert data["decided_by_user_id"] == user_a.id

    # Verify audit row for reject
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "reject",
            AuditLog.entity_id == approval.id,
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == user_a.email
    assert audit.details["decision_note"] == "Salary too high"


def test_member_role_gets_403(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # Create a member user in Tenant A
    member = create_tenant_user(
        session=session,
        tenant_id=tenant_a["tenant"].id,
        email="member@alpha.com",
        role=UserRole.MEMBER,
    )

    approval = approval_service.request_approval(
        session=session,
        tenant_id=tenant_a["tenant"].id,
        action_type=ApprovalActionType.SHORTLIST,
        target_type="application",
        target_id=103,
        payload=None,
        requested_by=tenant_a["user"].id,
    )

    # Member tries to approve -> 403
    res_app = client.post(
        f"/approvals/{approval.id}/approve",
        headers=member["headers"],
        json={"note": "I approve this"},
    )
    assert res_app.status_code == 403
    assert "admin or approver" in res_app.json()["detail"].lower()

    # Member tries to reject -> 403
    res_rej = client.post(
        f"/approvals/{approval.id}/reject",
        headers=member["headers"],
        json={"note": "I reject this"},
    )
    assert res_rej.status_code == 403


def test_approving_twice_gives_409(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    approval = approval_service.request_approval(
        session=session,
        tenant_id=tenant_a["tenant"].id,
        action_type=ApprovalActionType.SHORTLIST,
        target_type="application",
        target_id=104,
        payload=None,
        requested_by=tenant_a["user"].id,
    )

    # First approve succeeds
    res1 = client.post(
        f"/approvals/{approval.id}/approve",
        headers=tenant_a["headers"],
    )
    assert res1.status_code == 200

    # Second approve gives 409
    res2 = client.post(
        f"/approvals/{approval.id}/approve",
        headers=tenant_a["headers"],
    )
    assert res2.status_code == 409
    assert "already decided" in res2.json()["detail"].lower()

    # Rejecting an already approved gives 409 as well
    res3 = client.post(
        f"/approvals/{approval.id}/reject",
        headers=tenant_a["headers"],
    )
    assert res3.status_code == 409


def test_tenant_isolation_cannot_see_or_approve_other_tenant(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    approval_a = approval_service.request_approval(
        session=session,
        tenant_id=tenant_a["tenant"].id,
        action_type=ApprovalActionType.SHORTLIST,
        target_type="application",
        target_id=105,
        payload={"secret": "alpha data"},
        requested_by=tenant_a["user"].id,
    )

    # Tenant B tries to GET Tenant A's approval -> 404
    res_get = client.get(
        f"/approvals/{approval_a.id}",
        headers=tenant_b["headers"],
    )
    assert res_get.status_code == 404

    # Tenant B tries to approve Tenant A's approval -> 404
    res_app = client.post(
        f"/approvals/{approval_a.id}/approve",
        headers=tenant_b["headers"],
    )
    assert res_app.status_code == 404

    # Tenant B tries to reject Tenant A's approval -> 404
    res_rej = client.post(
        f"/approvals/{approval_a.id}/reject",
        headers=tenant_b["headers"],
    )
    assert res_rej.status_code == 404


def test_get_approvals_list_and_filter(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    u_id = tenant_a["user"].id
    t_id = tenant_a["tenant"].id

    app1 = approval_service.request_approval(
        session, t_id, ApprovalActionType.SHORTLIST, "application", 201, None, u_id
    )
    app2 = approval_service.request_approval(
        session, t_id, ApprovalActionType.OFFER_LETTER, "application", 202, None, u_id
    )

    # Approve app1
    client.post(f"/approvals/{app1.id}/approve", headers=tenant_a["headers"])

    # List all
    res_all = client.get("/approvals", headers=tenant_a["headers"])
    assert res_all.status_code == 200
    ids = [item["id"] for item in res_all.json()]
    assert app1.id in ids
    assert app2.id in ids

    # List pending only
    res_pending = client.get("/approvals?status=pending", headers=tenant_a["headers"])
    assert res_pending.status_code == 200
    pending_ids = [item["id"] for item in res_pending.json()]
    assert app1.id not in pending_ids
    assert app2.id in pending_ids


def test_require_approved_gate(
    two_tenants: dict[str, dict[str, Any]],
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]
    u_a = tenant_a["user"]
    t_a_id = tenant_a["tenant"].id
    t_b_id = tenant_b["tenant"].id

    # 1. Pending approval fails
    pending_app = approval_service.request_approval(
        session, t_a_id, ApprovalActionType.SHORTLIST, "application", 301, None, u_a.id
    )
    with pytest.raises(ApprovalRequiredException) as exc_info:
        approval_service.require_approved(
            session=session,
            approval_id=pending_app.id,
            tenant_id=t_a_id,
            expected_action_type=ApprovalActionType.SHORTLIST,
        )
    assert "not approved" in str(exc_info.value).lower()

    # 2. Rejected approval fails
    rejected_app = approval_service.request_approval(
        session, t_a_id, ApprovalActionType.SHORTLIST, "application", 302, None, u_a.id
    )
    approval_service.reject(session, rejected_app.id, u_a)
    with pytest.raises(ApprovalRequiredException) as exc_info:
        approval_service.require_approved(
            session=session,
            approval_id=rejected_app.id,
            tenant_id=t_a_id,
            expected_action_type=ApprovalActionType.SHORTLIST,
        )
    assert "not approved" in str(exc_info.value).lower()

    # 3. Wrong action type fails
    approved_app = approval_service.request_approval(
        session, t_a_id, ApprovalActionType.SHORTLIST, "application", 303, None, u_a.id
    )
    approval_service.approve(session, approved_app.id, u_a)

    with pytest.raises(ApprovalRequiredException) as exc_info:
        approval_service.require_approved(
            session=session,
            approval_id=approved_app.id,
            tenant_id=t_a_id,
            expected_action_type=ApprovalActionType.OFFER_LETTER,  # expected offer_letter, got shortlist
        )
    assert "action mismatch" in str(exc_info.value).lower()

    # 4. Cross-tenant fails
    with pytest.raises(ApprovalRequiredException) as exc_info:
        approval_service.require_approved(
            session=session,
            approval_id=approved_app.id,
            tenant_id=t_b_id,  # wrong tenant
            expected_action_type=ApprovalActionType.SHORTLIST,
        )
    assert "tenant mismatch" in str(exc_info.value).lower()

    # 5. Non-existent approval fails
    with pytest.raises(ApprovalRequiredException) as exc_info:
        approval_service.require_approved(
            session=session,
            approval_id=999999,
            tenant_id=t_a_id,
            expected_action_type=ApprovalActionType.SHORTLIST,
        )
    assert "does not exist" in str(exc_info.value).lower()

    # 6. Happy path succeeds
    gate_result = approval_service.require_approved(
        session=session,
        approval_id=approved_app.id,
        tenant_id=t_a_id,
        expected_action_type=ApprovalActionType.SHORTLIST,
    )
    assert gate_result.id == approved_app.id
    assert gate_result.status == ApprovalStatus.APPROVED.value


def test_approval_required_http_exception_mapping(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    pending_app = approval_service.request_approval(
        session,
        tenant_a["tenant"].id,
        ApprovalActionType.OFFER_LETTER,
        "application",
        500,
        None,
        tenant_a["user"].id,
    )

    # Temporary endpoint to verify exception handler maps ApprovalRequiredException to 403
    @client.app.get("/test-gated-action")
    def gated_endpoint() -> dict[str, str]:
        approval_service.require_approved(
            session=session,
            approval_id=pending_app.id,
            tenant_id=tenant_a["tenant"].id,
            expected_action_type=ApprovalActionType.OFFER_LETTER,
        )
        return {"status": "released"}

    res = client.get("/test-gated-action")
    assert res.status_code == 403
    assert "not approved" in res.json()["detail"].lower()
