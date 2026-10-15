from typing import Any
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import AuditLog, Tenant, User


def test_register_tenant(client: TestClient, session: Session) -> None:
    payload = {
        "company_name": "Acme Inc",
        "email": "owner@acme.com",
        "password": "securepassword123",
    }
    response = client.post("/auth/register-tenant", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify tenant & user created in DB
    user = session.exec(select(User).where(User.email == "owner@acme.com")).first()
    assert user is not None
    assert user.role == "admin"
    tenant = session.get(Tenant, user.tenant_id)
    assert tenant is not None
    assert tenant.name == "Acme Inc"

    # Verify audit log entry was written
    audit_entry = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant.id,
            AuditLog.action == "register_tenant",
        )
    ).first()
    assert audit_entry is not None
    assert audit_entry.actor_name == "owner@acme.com"
    assert audit_entry.entity_type == "tenant"
    assert audit_entry.details is not None
    assert audit_entry.details.get("company_name") == "Acme Inc"
    assert "password" not in audit_entry.details


def test_register_tenant_duplicate_email(client: TestClient) -> None:
    payload = {
        "company_name": "First Corp",
        "email": "duplicate@test.com",
        "password": "password123",
    }
    resp1 = client.post("/auth/register-tenant", json=payload)
    assert resp1.status_code == 200

    payload2 = {
        "company_name": "Second Corp",
        "email": "duplicate@test.com",
        "password": "password456",
    }
    resp2 = client.post("/auth/register-tenant", json=payload2)
    assert resp2.status_code == 400
    assert "already registered" in resp2.json()["detail"].lower()


def test_login_success(client: TestClient, session: Session) -> None:
    # Register first
    client.post(
        "/auth/register-tenant",
        json={
            "company_name": "Login Corp",
            "email": "login@test.com",
            "password": "mypassword123",
        },
    )

    # Login with form data
    response = client.post(
        "/auth/login",
        data={"username": "login@test.com", "password": "mypassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify audit log entry for login
    user = session.exec(select(User).where(User.email == "login@test.com")).first()
    assert user is not None
    login_audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == user.tenant_id,
            AuditLog.action == "login",
        )
    ).first()
    assert login_audit is not None
    assert login_audit.actor_name == "login@test.com"
    assert login_audit.entity_type == "user"
    assert login_audit.entity_id == user.id
    assert "password" not in str(login_audit.details)


def test_login_wrong_password(client: TestClient) -> None:
    client.post(
        "/auth/register-tenant",
        json={
            "company_name": "Wrong Pass Corp",
            "email": "wrongpass@test.com",
            "password": "correctpassword",
        },
    )

    response = client.post(
        "/auth/login",
        data={"username": "wrongpass@test.com", "password": "incorrectpassword"},
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_auth_me(client: TestClient) -> None:
    reg_resp = client.post(
        "/auth/register-tenant",
        json={
            "company_name": "Profile Corp",
            "email": "profile@test.com",
            "password": "profilepass123",
        },
    )
    token = reg_resp.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile@test.com"
    assert data["role"] == "admin"
    assert "id" in data
    assert "tenant_id" in data


def test_auth_me_without_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_auth_me_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert response.status_code == 401


def test_tenant_isolation_helper(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    # Verify Tenant A credentials fetch Tenant A info
    res_a = client.get("/auth/me", headers=two_tenants["tenant_a"]["headers"])
    assert res_a.status_code == 200
    user_a_info = res_a.json()

    # Verify Tenant B credentials fetch Tenant B info
    res_b = client.get("/auth/me", headers=two_tenants["tenant_b"]["headers"])
    assert res_b.status_code == 200
    user_b_info = res_b.json()

    # Check isolation between the two tenants
    assert user_a_info["tenant_id"] != user_b_info["tenant_id"]
    assert user_a_info["email"] == "admin@alpha.com"
    assert user_b_info["email"] == "admin@beta.com"
    assert user_a_info["tenant_id"] == two_tenants["tenant_a"]["tenant"].id
    assert user_b_info["tenant_id"] == two_tenants["tenant_b"]["tenant"].id


def test_require_role(two_tenants: dict[str, dict[str, Any]], client: TestClient, session: Session) -> None:
    from app.deps import require_role
    from app.models import UserRole
    from fastapi import Depends

    # Define a temporary route testing require_role
    @client.app.get("/test-admin-only")
    def admin_only_endpoint(user: Any = Depends(require_role(UserRole.ADMIN))) -> dict[str, str]:
        return {"ok": "admin"}

    @client.app.get("/test-member-only")
    def member_only_endpoint(user: Any = Depends(require_role(UserRole.MEMBER))) -> dict[str, str]:
        return {"ok": "member"}

    # Tenant A admin should access admin endpoint
    res1 = client.get("/test-admin-only", headers=two_tenants["tenant_a"]["headers"])
    assert res1.status_code == 200

    # Tenant A admin is not member -> 403
    res2 = client.get("/test-member-only", headers=two_tenants["tenant_a"]["headers"])
    assert res2.status_code == 403
