from typing import Any
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import AuditLog


def test_create_job_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    payload = {
        "title": "Senior Backend Engineer",
        "description": "Python, FastAPI, SQLModel expert needed",
        "status": "open",
    }
    response = client.post("/jobs", headers=tenant_a["headers"], json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["status"] == "open"
    assert "id" in data
    assert "created_at" in data

    # Verify audit log was recorded
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "create_job",
            AuditLog.entity_id == data["id"],
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == tenant_a["user"].email
    assert audit.details["title"] == payload["title"]


def test_list_and_get_jobs(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # Create two jobs
    r1 = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "DevOps Engineer", "description": "K8s, AWS"},
    )
    r2 = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Product Designer", "description": "Figma, UI/UX"},
    )
    j1_id = r1.json()["id"]
    j2_id = r2.json()["id"]

    # List jobs
    list_res = client.get("/jobs", headers=tenant_a["headers"])
    assert list_res.status_code == 200
    job_ids = [j["id"] for j in list_res.json()]
    assert j1_id in job_ids
    assert j2_id in job_ids

    # Get one job
    get_res = client.get(f"/jobs/{j1_id}", headers=tenant_a["headers"])
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "DevOps Engineer"


def test_cross_tenant_job_isolation(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    # Tenant A creates a job
    res = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Secret Project Lead", "description": "Top secret"},
    )
    job_a_id = res.json()["id"]

    # Tenant B tries to GET Tenant A's job -> 404
    cross_res = client.get(f"/jobs/{job_a_id}", headers=tenant_b["headers"])
    assert cross_res.status_code == 404
    assert "not found" in cross_res.json()["detail"].lower()

    # Tenant B lists jobs -> should not contain Tenant A's job
    list_b = client.get("/jobs", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert job_a_id not in [j["id"] for j in list_b.json()]
