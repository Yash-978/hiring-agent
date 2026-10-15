from typing import Any
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Approval, ApprovalActionType, ApprovalStatus, AuditLog


def test_create_application_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # Create candidate and job in Tenant A
    cand_resp = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Diana Prince", "email": "diana@themyscira.gov"},
    )
    job_resp = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Security Specialist", "description": "Protecting systems"},
    )
    cand_id = cand_resp.json()["id"]
    job_id = job_resp.json()["id"]

    # Create application
    app_resp = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand_id, "job_id": job_id},
    )
    assert app_resp.status_code == 201
    data = app_resp.json()
    assert data["candidate_id"] == cand_id
    assert data["job_id"] == job_id
    assert data["candidate_name"] == "Diana Prince"
    assert data["job_title"] == "Security Specialist"
    assert data["status"] == "new"
    assert "id" in data
    assert "created_at" in data

    # Verify audit log was recorded
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "create_application",
            AuditLog.entity_id == data["id"],
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == tenant_a["user"].email
    assert audit.details["candidate_id"] == cand_id
    assert audit.details["job_id"] == job_id


def test_list_and_get_applications(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # Create candidate and job
    c = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bruce Wayne", "email": "bruce@waynecorp.com"},
    ).json()
    j = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "CEO", "description": "Executive duties"},
    ).json()

    # Create application
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": c["id"], "job_id": j["id"]},
    ).json()
    app_id = app["id"]

    # List applications -> includes candidate_name and job_title
    list_res = client.get("/applications", headers=tenant_a["headers"])
    assert list_res.status_code == 200
    apps = list_res.json()
    target = next((item for item in apps if item["id"] == app_id), None)
    assert target is not None
    assert target["candidate_name"] == "Bruce Wayne"
    assert target["job_title"] == "CEO"

    # Get single application -> includes candidate_name and job_title
    get_res = client.get(f"/applications/{app_id}", headers=tenant_a["headers"])
    assert get_res.status_code == 200
    single = get_res.json()
    assert single["id"] == app_id
    assert single["candidate_name"] == "Bruce Wayne"
    assert single["job_title"] == "CEO"


def test_cross_tenant_application_get_isolation(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    c = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Clark Kent", "email": "clark@dailyplanet.com"},
    ).json()
    j = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Journalist", "description": "News reporter"},
    ).json()
    app_a = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": c["id"], "job_id": j["id"]},
    ).json()

    # Tenant B tries to GET Tenant A's application -> 404
    cross_res = client.get(
        f"/applications/{app_a['id']}", headers=tenant_b["headers"]
    )
    assert cross_res.status_code == 404
    assert "not found" in cross_res.json()["detail"].lower()

    # Tenant B list does not contain Tenant A's application
    list_b = client.get("/applications", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert app_a["id"] not in [a["id"] for a in list_b.json()]


def test_create_application_with_foreign_tenant_candidate_id_fails(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    # Tenant A creates candidate
    cand_a = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Alpha Candidate", "email": "alpha.cand@example.com"},
    ).json()

    # Tenant B creates job
    job_b = client.post(
        "/jobs",
        headers=tenant_b["headers"],
        json={"title": "Beta Job", "description": "Beta tenant work"},
    ).json()

    # Tenant B attempts to create Application using Tenant A's candidate_id -> 404
    res = client.post(
        "/applications",
        headers=tenant_b["headers"],
        json={"candidate_id": cand_a["id"], "job_id": job_b["id"]},
    )
    assert res.status_code == 404
    assert "candidate" in res.json()["detail"].lower()


def test_create_application_with_foreign_tenant_job_id_fails(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    # Tenant A creates job
    job_a = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Alpha Job", "description": "Alpha tenant work"},
    ).json()

    # Tenant B creates candidate
    cand_b = client.post(
        "/candidates",
        headers=tenant_b["headers"],
        json={"full_name": "Beta Candidate", "email": "beta.cand@example.com"},
    ).json()

    # Tenant B attempts to create Application using Tenant A's job_id -> 404
    res = client.post(
        "/applications",
        headers=tenant_b["headers"],
        json={"candidate_id": cand_b["id"], "job_id": job_a["id"]},
    )
    assert res.status_code == 404
    assert "job" in res.json()["detail"].lower()


def test_analyze_application_success(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # Create candidate and job
    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Alice Smith", "email": "alice@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={
            "title": "Backend Engineer",
            "description": "Python, FastAPI, PostgreSQL experience required",
        },
    ).json()

    # Create application
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()
    app_id = app["id"]

    # Upload resume as TXT
    resume_text = "Alice Smith\n5 years Python, FastAPI, SQL"
    files = {"file": ("resume.txt", resume_text, "text/plain")}
    resp = client.post(
        f"/applications/{app_id}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == app_id
    assert data["status"] == "analyzed"
    assert data["score"] == 85
    assert data["score_reasoning"] == "Strong match for required skills"

    # Verify exactly one pending shortlist approval was created
    approvals = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_a["tenant"].id,
            Approval.action_type == ApprovalActionType.SHORTLIST.value,
            Approval.target_type == "application",
            Approval.target_id == app_id,
            Approval.status == ApprovalStatus.PENDING.value,
        )
    ).all()
    assert len(approvals) == 1
    assert approvals[0].payload["score"] == 85

    # Verify audit log entries
    audits = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.entity_type == "application",
            AuditLog.entity_id == app_id,
        )
    ).all()
    actions = {a.action for a in audits}
    assert "analyze_resume" in actions
    assert "create_application" in actions
    # Check agent audit
    agent_audit = next(
        a for a in audits
        if (a.actor_type.value if hasattr(a.actor_type, "value") else a.actor_type) == "agent"
    )
    assert agent_audit.actor_name == "resume_agent"
    assert agent_audit.details["score"] == 85


def test_analyze_application_bad_file_type(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bob", "email": "bob@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Dev", "description": "Python"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    # Upload unsupported file type
    files = {"file": ("resume.docx", b"fake", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 415
    assert "only pdf and txt" in resp.json()["detail"].lower()


def test_analyze_application_llm_failure_creates_no_approval(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Carol", "email": "carol@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Dev", "description": "Python"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()
    app_id = app["id"]

    # Use a schema that FakeLLMClient doesn't handle to trigger LLMError
    from app.agents.llm import FakeLLMClient
    from app.agents.resume_agent import ResumeAnalysis

    # Monkey-patch to simulate LLM failure
    original_generate = FakeLLMClient.generate_json

    def failing_generate(self, system: str, prompt: str, schema: type[ResumeAnalysis]) -> ResumeAnalysis:
        if schema is ResumeAnalysis:
            from app.agents.llm import LLMError
            raise LLMError("simulated failure")
        return original_generate(self, system, prompt, schema)

    FakeLLMClient.generate_json = failing_generate  # type: ignore[assignment]
    try:
        files = {"file": ("resume.txt", "Carol resume", "text/plain")}
        resp = client.post(
            f"/applications/{app_id}/analyze",
            headers=tenant_a["headers"],
            files=files,
        )
        assert resp.status_code == 502
    finally:
        FakeLLMClient.generate_json = original_generate  # type: ignore[assignment]

    # Verify no approval was created
    approvals = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_a["tenant"].id,
            Approval.target_type == "application",
            Approval.target_id == app_id,
        )
    ).all()
    assert len(approvals) == 0

    # Verify analysis_failed audit was logged
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "analysis_failed",
            AuditLog.entity_id == app_id,
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == "resume_agent"


def test_analyze_application_cross_tenant_isolation(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Dave", "email": "dave@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Dev", "description": "Python"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    # Tenant B tries to analyze Tenant A's application -> 404
    files = {"file": ("resume.txt", "Dave resume", "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_b["headers"],
        files=files,
    )
    assert resp.status_code == 404
