from typing import Any
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import get_settings
from app.models import Application, Approval, ApprovalActionType, ApprovalStatus, AuditLog

# A resume long enough to pass the 200-character minimum that also contains the
# exact evidence quotes the fake LLM client returns, so verification succeeds.
LONG_RESUME = (
    "Alice Smith\n"
    "Email: alice@example.com\n"
    "Backend Engineer with 5 years Python experience building APIs.\n"
    "Built services with Python and FastAPI and shipped them with Docker.\n"
    "Bachelor of Science in Computer Science from a state university.\n"
    "Worked with PostgreSQL, Redis and CI pipelines across several teams.\n"
)


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
    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app_id}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == app_id
    assert data["status"] == "analyzed"
    assert data["score"] == 90.0
    assert data["score_reasoning"] == "shortlist (confidence: medium)"

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
    payload = approvals[0].payload
    assert payload["score"] == 90.0
    assert payload["prompt_version"] == "resume_analysis_v2"
    assert payload["model"] == "fake"
    assert payload["flags"] == []
    assert payload["breakdown"]["must_have"]["ratio"] == 1.0
    criteria = payload["analysis"]["criteria"]
    assert len(criteria) == 4
    assert all(c["evidence_verified"] for c in criteria)

    # Verify the full analysis bundle is stored on the Application itself
    stored = session.get(Application, app_id)
    assert stored is not None
    assert stored.analysis is not None
    assert stored.analysis["score"] == 90.0
    assert stored.analysis["prompt_version"] == "resume_analysis_v2"
    assert stored.analysis["model"] == "fake"
    assert stored.analysis["flags"] == []
    assert stored.analysis["breakdown"]["must_have"]["ratio"] == 1.0

    # The original upload is saved under STORAGE_DIR with a server-made name
    assert stored.resume_path == f"tenants/{tenant_a['tenant'].id}/applications/{app_id}/resume.txt"
    saved = get_settings().STORAGE_DIR / stored.resume_path
    assert saved.exists()
    assert saved.read_bytes() == LONG_RESUME.encode("utf-8")

    # Verify audit log entries
    audits = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.entity_type == "application",
            AuditLog.entity_id == app_id,
        )
    ).all()
    actions = {a.action for a in audits}
    assert "analysis_completed" in actions
    assert "create_application" in actions
    # Check agent audit
    agent_audit = next(
        a for a in audits
        if (a.actor_type.value if hasattr(a.actor_type, "value") else a.actor_type) == "agent"
    )
    assert agent_audit.actor_name == "resume_agent"
    assert agent_audit.details["score"] == 90.0
    assert agent_audit.details["model"] == "fake"
    assert agent_audit.details["criteria_count"] == 4
    assert len(agent_audit.details["resume_sha8"]) == 8


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
        files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
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
    session: Session,
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

    # Nothing was stored by the rejected cross-tenant request
    stored = session.get(Application, app["id"])
    assert stored is not None
    assert stored.analysis is None
    assert stored.resume_path is None


def test_get_application_audit_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # Create candidate, job, application
    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Eve", "email": "eve@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Dev", "description": "Python, FastAPI"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()
    app_id = app["id"]

    # Analyze to generate audit entries
    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    client.post(
        f"/applications/{app_id}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )

    # GET audit
    audit_res = client.get(
        f"/applications/{app_id}/audit",
        headers=tenant_a["headers"],
    )
    assert audit_res.status_code == 200
    audits = audit_res.json()
    assert len(audits) >= 2
    actions = {a["action"] for a in audits}
    assert "create_application" in actions
    assert "analysis_completed" in actions
    # Check ordering: oldest first (created_at asc)
    created_times = [a["created_at"] for a in audits]
    assert created_times == sorted(created_times)


def test_get_application_audit_cross_tenant_isolation(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Frank", "email": "frank@example.com"},
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

    # Tenant B tries to GET audit for Tenant A's application -> 404
    cross_res = client.get(
        f"/applications/{app_id}/audit",
        headers=tenant_b["headers"],
    )
    assert cross_res.status_code == 404
    assert "not found" in cross_res.json()["detail"].lower()


def test_analyze_application_short_resume_returns_422(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Shorty", "email": "shorty@example.com"},
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

    # Resume text below the 200-character minimum -> 422, no approval created.
    files = {"file": ("resume.txt", "Too short", "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 422

    approvals = session.exec(
        select(Approval).where(
            Approval.target_type == "application",
            Approval.target_id == app["id"],
        )
    ).all()
    assert approvals == []


def test_analyze_application_flags_name_and_email_mismatch(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    # The stored candidate differs from what the fake LLM extracts (Alice Smith).
    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bob Jones", "email": "bob@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
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

    approval = session.exec(
        select(Approval).where(
            Approval.target_type == "application",
            Approval.target_id == app["id"],
        )
    ).first()
    assert approval is not None
    assert set(approval.payload["flags"]) == {"name_mismatch", "email_mismatch"}


def test_analyze_application_unverified_evidence_counts_as_unknown(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Alice Smith", "email": "alice@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI, Docker"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    from app.agents.llm import FakeLLMClient

    original_generate = FakeLLMClient.generate_json

    def patched_generate(self, system: str, prompt: str, schema: Any) -> Any:
        result = original_generate(self, system, prompt, schema)
        if schema.__name__ == "ResumeAnalysis":
            # A quote that does not appear anywhere in the resume.
            result.criteria[0].evidence = "a fabricated quote not in the resume"
        return result

    FakeLLMClient.generate_json = patched_generate  # type: ignore[assignment]
    try:
        files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
        resp = client.post(
            f"/applications/{app['id']}/analyze",
            headers=tenant_a["headers"],
            files=files,
        )
    finally:
        FakeLLMClient.generate_json = original_generate  # type: ignore[assignment]

    assert resp.status_code == 200

    approval = session.exec(
        select(Approval).where(
            Approval.target_type == "application",
            Approval.target_id == app["id"],
        )
    ).first()
    assert approval is not None
    payload = approval.payload
    assert payload["analysis"]["criteria"][0]["evidence_verified"] is False
    # Unverified positive verdict is treated as unknown: 55.0 not 90.0.
    assert payload["score"] == 55.0


def test_analyze_application_ignores_client_filename(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    """The stored upload uses a server-made name, never the client filename."""
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Alice Smith", "email": "alice@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Backend Engineer", "description": "Python, FastAPI, Docker"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    # A traversal-style filename must not influence where the file lands.
    files = {"file": ("../../evil.exe", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200

    stored = session.get(Application, app["id"])
    assert stored is not None
    assert stored.resume_path == (
        f"tenants/{tenant_a['tenant'].id}/applications/{app['id']}/resume.txt"
    )
    saved = get_settings().STORAGE_DIR / stored.resume_path
    assert saved.exists()
    assert saved.name == "resume.txt"


def test_resume_extension_maps_known_content_types() -> None:
    """Only whitelisted content types produce a real extension."""
    from app.services.application_service import _resume_extension

    assert _resume_extension("application/pdf") == "pdf"
    assert _resume_extension("text/plain; charset=utf-8") == "txt"
    assert (
        _resume_extension(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        == "docx"
    )
    assert _resume_extension("application/octet-stream") == "bin"
    assert _resume_extension(None) == "bin"


def _analyzed_application(
    client: TestClient,
    headers: dict[str, str],
    *,
    candidate_name: str = "Alice Smith",
    candidate_email: str = "alice@example.com",
    job_title: str = "Backend Engineer",
    job_description: str = "Python, FastAPI, Docker",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a candidate, job and analyzed application; return (candidate, app)."""
    cand = client.post(
        "/candidates",
        headers=headers,
        json={"full_name": candidate_name, "email": candidate_email},
    ).json()
    job = client.post(
        "/jobs",
        headers=headers,
        json={"title": job_title, "description": job_description},
    ).json()
    app = client.post(
        "/applications",
        headers=headers,
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()
    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app['id']}/analyze",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 200
    return cand, app


def test_get_application_analysis_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    _cand, app = _analyzed_application(client, tenant_a["headers"])

    resp = client.get(
        f"/applications/{app['id']}/analysis", headers=tenant_a["headers"]
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["application_id"] == app["id"]
    assert data["job"]["id"] == app["job_id"]
    assert data["job"]["title"] == "Backend Engineer"

    assert data["candidate"]["full_name"] == "Alice Smith"
    assert data["candidate"]["email"] == "alice@example.com"
    assert data["candidate"]["total_years_experience"] == 5.0

    assert data["score"] == 90.0
    assert data["breakdown"]["must_have"]["ratio"] == 1.0
    assert data["breakdown"]["must_have"]["count"] == 2
    assert data["breakdown"]["nice_to_have"]["ratio"] == 0.5

    assert len(data["criteria"]) == 4
    assert data["criteria"][0]["criterion"] == "Python"
    assert data["criteria"][0]["evidence_verified"] is True

    assert data["recommendation"] == "shortlist"
    assert data["confidence"] == "medium"
    assert data["flags"] == []
    assert data["model"] == "fake"
    assert data["prompt_version"] == "resume_analysis_v2"
    assert data["resume_available"] is True


def test_get_application_analysis_before_analysis_is_404(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Carol Danvers", "email": "carol@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Pilot", "description": "Fly planes"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    resp = client.get(
        f"/applications/{app['id']}/analysis", headers=tenant_a["headers"]
    )
    assert resp.status_code == 404
    assert "not been analyzed" in resp.json()["detail"].lower()


def test_get_application_analysis_cross_tenant_is_404(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    _cand, app = _analyzed_application(client, tenant_a["headers"])

    resp = client.get(
        f"/applications/{app['id']}/analysis", headers=tenant_b["headers"]
    )
    assert resp.status_code == 404


def test_download_application_resume_happy_path(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    _cand, app = _analyzed_application(client, tenant_a["headers"])

    resp = client.get(
        f"/applications/{app['id']}/resume", headers=tenant_a["headers"]
    )
    assert resp.status_code == 200
    assert resp.content == LONG_RESUME.encode("utf-8")
    assert resp.headers["content-type"].startswith("text/plain")

    # The download is audited for the owning tenant.
    audit = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.action == "resume_downloaded",
            AuditLog.entity_id == app["id"],
        )
    ).first()
    assert audit is not None
    assert audit.actor_name == tenant_a["user"].email


def test_download_application_resume_not_available_is_404(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Scott Summers", "email": "scott@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={"title": "Field Lead", "description": "Lead the field team"},
    ).json()
    app = client.post(
        "/applications",
        headers=tenant_a["headers"],
        json={"candidate_id": cand["id"], "job_id": job["id"]},
    ).json()

    resp = client.get(
        f"/applications/{app['id']}/resume", headers=tenant_a["headers"]
    )
    assert resp.status_code == 404


def test_download_application_resume_cross_tenant_is_404(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    _cand, app = _analyzed_application(client, tenant_a["headers"])

    resp = client.get(
        f"/applications/{app['id']}/resume", headers=tenant_b["headers"]
    )
    assert resp.status_code == 404
