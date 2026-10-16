"""Tests for letters routes and offer flow."""

from typing import Any
from datetime import date
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Approval, ApprovalActionType, ApprovalStatus, AuditLog, Letter
from app.services import approval_service
from tests.conftest import create_tenant_user

# Resume text long enough to pass the 200-character minimum for analysis.
LONG_RESUME = (
    "Alice Smith\n"
    "Email: alice@example.com\n"
    "Backend Engineer with 5 years Python experience building APIs.\n"
    "Built services with Python and FastAPI and shipped them with Docker.\n"
    "Bachelor of Science in Computer Science from a state university.\n"
    "Worked with PostgreSQL, Redis and CI pipelines across several teams.\n"
)


def test_letter_flow_requires_approved_shortlist(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
) -> None:
    """Offer draft fails with 403 if shortlist approval not approved."""
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

    # Upload resume and analyze
    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app_id}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200

    # Try to create offer draft WITHOUT approving shortlist -> 403
    offer_data = {"salary": 100000, "currency": "USD", "start_date": "2026-01-15"}
    resp = client.post(
        f"/applications/{app_id}/offer-draft",
        headers=tenant_a["headers"],
        json=offer_data,
    )
    assert resp.status_code == 403
    assert "shortlist approval required" in resp.json()["detail"].lower()


def test_letter_generate_and_download_flow(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    """Full flow: analyze -> approve shortlist -> offer draft -> approve offer -> generate -> download."""
    tenant_a = two_tenants["tenant_a"]

    # Create candidate and job
    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Bob Jones", "email": "bob@example.com"},
    ).json()
    job = client.post(
        "/jobs",
        headers=tenant_a["headers"],
        json={
            "title": "Senior Engineer",
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

    # Upload resume and analyze
    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    resp = client.post(
        f"/applications/{app_id}/analyze",
        headers=tenant_a["headers"],
        files=files,
    )
    assert resp.status_code == 200

    # Find and approve the shortlist approval
    shortlist_approval = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_a["tenant"].id,
            Approval.action_type == ApprovalActionType.SHORTLIST.value,
            Approval.target_type == "application",
            Approval.target_id == app_id,
        )
    ).first()
    assert shortlist_approval is not None

    approve_resp = client.post(
        f"/approvals/{shortlist_approval.id}/approve",
        headers=tenant_a["headers"],
    )
    assert approve_resp.status_code == 200

    # Create offer draft
    offer_data = {"salary": 120000, "currency": "USD", "start_date": "2026-02-01"}
    resp = client.post(
        f"/applications/{app_id}/offer-draft",
        headers=tenant_a["headers"],
        json=offer_data,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "offer_drafted"

    # Find the letter created
    letter = session.exec(
        select(Letter).where(Letter.application_id == app_id)
    ).first()
    assert letter is not None
    letter_id = letter.id

    # Verify letter exists but has no file_path yet
    assert letter.file_path is None

    # GET letter -> 200
    get_resp = client.get(f"/letters/{letter_id}", headers=tenant_a["headers"])
    assert get_resp.status_code == 200

    # Find and approve the offer_letter approval
    offer_approval = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_a["tenant"].id,
            Approval.action_type == ApprovalActionType.OFFER_LETTER.value,
            Approval.target_type == "letter",
            Approval.target_id == letter_id,
        )
    ).first()
    assert offer_approval is not None

    approve_resp = client.post(
        f"/approvals/{offer_approval.id}/approve",
        headers=tenant_a["headers"],
    )
    assert approve_resp.status_code == 200

    # Generate DOCX (requires offer approval)
    gen_resp = client.post(
        f"/letters/{letter_id}/generate", headers=tenant_a["headers"]
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["file_path"] is not None

    # Download after generate -> 200 with correct content type
    download_resp = client.get(
        f"/letters/{letter_id}/download", headers=tenant_a["headers"]
    )
    assert download_resp.status_code == 200
    assert (
        download_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "offer_letter" in download_resp.headers["content-disposition"]

    # Verify audit logs
    audits = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a["tenant"].id,
            AuditLog.entity_type == "letter",
            AuditLog.entity_id == letter_id,
        )
    ).all()
    actions = {a.action for a in audits}
    assert "draft_offer" in actions
    assert "letter_generated" in actions
    assert "letter_downloaded" in actions


def test_cross_tenant_letter_isolation(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    """Tenant B cannot access Tenant A's letters."""
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    # Tenant A creates candidate, job, application, analyzes, approves, creates offer
    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Carol White", "email": "carol@example.com"},
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

    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    client.post(f"/applications/{app_id}/analyze", headers=tenant_a["headers"], files=files)

    shortlist_approval = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_a["tenant"].id,
            Approval.action_type == ApprovalActionType.SHORTLIST.value,
            Approval.target_type == "application",
            Approval.target_id == app_id,
        )
    ).first()
    client.post(
        f"/approvals/{shortlist_approval.id}/approve", headers=tenant_a["headers"]
    )

    offer_data = {"salary": 90000, "currency": "USD", "start_date": "2026-03-01"}
    client.post(
        f"/applications/{app_id}/offer-draft", headers=tenant_a["headers"], json=offer_data
    )

    letter = session.exec(
        select(Letter).where(Letter.application_id == app_id)
    ).first()
    letter_id = letter.id

    # Tenant B tries to GET Tenant A's letter -> 404
    cross_resp = client.get(f"/letters/{letter_id}", headers=tenant_b["headers"])
    assert cross_resp.status_code == 404

    # Tenant B tries to generate Tenant A's letter -> 404
    gen_resp = client.post(
        f"/letters/{letter_id}/generate", headers=tenant_b["headers"]
    )
    assert gen_resp.status_code == 404

    # Tenant B tries to download Tenant A's letter -> 404
    download_resp = client.get(
        f"/letters/{letter_id}/download", headers=tenant_b["headers"]
    )
    assert download_resp.status_code == 404


def test_download_before_approval_returns_403(
    two_tenants: dict[str, dict[str, Any]],
    client: TestClient,
    session: Session,
) -> None:
    """Download fails with 403 if offer approval not approved."""
    tenant_a = two_tenants["tenant_a"]

    cand = client.post(
        "/candidates",
        headers=tenant_a["headers"],
        json={"full_name": "Dave Green", "email": "dave@example.com"},
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

    files = {"file": ("resume.txt", LONG_RESUME, "text/plain")}
    client.post(f"/applications/{app_id}/analyze", headers=tenant_a["headers"], files=files)

    shortlist_approval = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_a["tenant"].id,
            Approval.action_type == ApprovalActionType.SHORTLIST.value,
            Approval.target_type == "application",
            Approval.target_id == app_id,
        )
    ).first()
    client.post(
        f"/approvals/{shortlist_approval.id}/approve", headers=tenant_a["headers"]
    )

    offer_data = {"salary": 80000, "currency": "USD", "start_date": "2026-04-01"}
    client.post(
        f"/applications/{app_id}/offer-draft", headers=tenant_a["headers"], json=offer_data
    )

    letter = session.exec(
        select(Letter).where(Letter.application_id == app_id)
    ).first()
    letter_id = letter.id

    # Generate the DOCX first
    client.post(f"/letters/{letter_id}/generate", headers=tenant_a["headers"])

    # Reject the offer approval
    offer_approval = session.exec(
        select(Approval).where(
            Approval.tenant_id == tenant_a["tenant"].id,
            Approval.action_type == ApprovalActionType.OFFER_LETTER.value,
            Approval.target_type == "letter",
            Approval.target_id == letter_id,
        )
    ).first()
    assert offer_approval is not None

    client.post(
        f"/approvals/{offer_approval.id}/reject",
        headers=tenant_a["headers"],
        json={"note": "Salary too low"},
    )

    # Try to download -> 403
    download_resp = client.get(
        f"/letters/{letter_id}/download", headers=tenant_a["headers"]
    )
    assert download_resp.status_code == 403
    assert "approval not approved" in download_resp.json()["detail"].lower()