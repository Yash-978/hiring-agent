from typing import Any
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import AuditLog


def test_create_candidate_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    payload = {
        "full_name": "Alice Wonder",
        "email": "alice@wonder.land",
        "resume_text": "Experienced full-stack developer with 6 years in React & Python.",
        "parsed_data": {"skills": ["Python", "FastAPI", "React"]},
    }
    response = client.post("/candidates", headers=tenant_a["headers"], json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == payload["full_name"]
    assert data["email"] == payload["email"]
    assert data["resume_text"] == payload["resume_text"]
    assert data["parsed_data"] == payload["parsed_data"]
    assert "id" in data
    assert "created_at" in data

    # Verify audit log was recorded and NEVER contains resume_text
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "create_candidate",
            AuditLog.entity_id == data["id"],
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == tenant_a["user"].email
    assert audit.details["full_name"] == payload["full_name"]
    assert audit.details["email"] == payload["email"]
    assert "resume_text" not in audit.details
    assert "resume" not in str(audit.details).lower()


def test_list_and_get_candidates(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    r1 = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bob Builder", "email": "bob@builder.com"},
    )
    r2 = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Charlie Brown", "email": "charlie@brown.com"},
    )
    c1_id = r1.json()["id"]
    c2_id = r2.json()["id"]

    # List candidates
    list_res = client.get("/candidates", headers=tenant_a["headers"])
    assert list_res.status_code == 200
    candidate_ids = [c["id"] for c in list_res.json()]
    assert c1_id in candidate_ids
    assert c2_id in candidate_ids

    # Get single candidate
    get_res = client.get(f"/candidates/{c1_id}", headers=tenant_a["headers"])
    assert get_res.status_code == 200
    assert get_res.json()["full_name"] == "Bob Builder"


def test_cross_tenant_candidate_isolation(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    res = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Tenant A Candidate", "email": "candidate.a@example.com"},
    )
    cand_a_id = res.json()["id"]

    # Tenant B tries to GET Tenant A's candidate -> 404
    cross_res = client.get(f"/candidates/{cand_a_id}", headers=tenant_b["headers"])
    assert cross_res.status_code == 404
    assert "not found" in cross_res.json()["detail"].lower()

    # Tenant B list does not include Tenant A's candidate
    list_b = client.get("/candidates", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert cand_a_id not in [c["id"] for c in list_b.json()]
