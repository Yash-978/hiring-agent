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


LONG_RESUME = (
    "Senior backend engineer with five years of hands-on experience building "
    "production services in Python and FastAPI. Comfortable with PostgreSQL "
    "and Docker, and used to owning services end to end including tests, "
    "deployment and on-call. Led a small team and mentored two junior "
    "engineers. Strong background in API design, data modelling and "
    "performance tuning. Available to start within four weeks."
)


def test_create_job_with_requirements_fields(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    payload = {
        "title": "Platform Engineer",
        "description": "Build and run the platform",
        "must_have_skills": ["Go", "Kubernetes"],
        "nice_to_have_skills": ["Terraform"],
        "min_years_experience": 4.0,
    }
    resp = client.post("/jobs", headers=tenant_a["headers"], json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["must_have_skills"] == ["Go", "Kubernetes"]
    assert data["nice_to_have_skills"] == ["Terraform"]
    assert data["min_years_experience"] == 4.0

    get_res = client.get(f"/jobs/{data['id']}", headers=tenant_a["headers"])
    assert get_res.status_code == 200
    got = get_res.json()
    assert got["must_have_skills"] == ["Go", "Kubernetes"]
    assert got["nice_to_have_skills"] == ["Terraform"]
    assert got["min_years_experience"] == 4.0


def test_create_job_requirements_default_to_empty(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    resp = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Product Designer", "description": "Figma work"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["must_have_skills"] == []
    assert data["nice_to_have_skills"] == []
    assert data["min_years_experience"] is None


def test_analyze_application_extracts_job_requirements_when_empty(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Alice Smith", "email": "alice.extract@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={
            "title": "Backend Engineer",
            "description": "Python, FastAPI, PostgreSQL experience required",
        },
    ).json()
    assert job["must_have_skills"] == []

    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200

    filled = client.get(
        f"/jobs/{job['id']}", headers=tenant_a["headers"]
    ).json()
    assert filled["must_have_skills"] == ["Python", "FastAPI"]
    assert filled["nice_to_have_skills"] == ["Docker"]
    assert filled["min_years_experience"] == 3.0


def test_analyze_application_keeps_existing_job_requirements(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bob Jones", "email": "bob.extract@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={
            "title": "Backend Engineer",
            "description": "Python, FastAPI, PostgreSQL experience required",
            "must_have_skills": ["Rust"],
            "nice_to_have_skills": ["Elixir"],
            "min_years_experience": 8.0,
        },
    ).json()

    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200

    unchanged = client.get(
        f"/jobs/{job['id']}", headers=tenant_a["headers"]
    ).json()
    assert unchanged["must_have_skills"] == ["Rust"]
    assert unchanged["nice_to_have_skills"] == ["Elixir"]
    assert unchanged["min_years_experience"] == 8.0

