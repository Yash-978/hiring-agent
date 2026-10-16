"""Tests for the developer scripts: try_resume.py, seed.py and dedupe_jobs.py."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

from sqlmodel import Session, select

from app.models import (
    Application,
    Approval,
    ApprovalActionType,
    AuditLog,
    Candidate,
    Job,
    Tenant,
    User,
    UserRole,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"
SAMPLES_DIR = BACKEND_DIR / "samples" / "resumes"


def _load_script(name: str) -> ModuleType:
    """Load a script from backend/scripts without requiring a package."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_job(session: Session, tenant_id: int) -> Job:
    job = Job(
        tenant_id=tenant_id,
        title="Backend Engineer",
        description="We need Python and FastAPI. Docker is a plus. 3 years.",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    assert job.id is not None
    return job


def test_sample_resumes_exist_and_are_long_enough() -> None:
    files = sorted(SAMPLES_DIR.glob("*.txt"))
    assert len(files) == 4
    for path in files:
        assert len(path.read_text(encoding="utf-8")) > 200


def test_read_sample_resumes_derives_name_and_email() -> None:
    seed = _load_script("seed")
    rows = seed.read_sample_resumes()
    assert len(rows) == 4
    names = [row[0] for row in rows]
    emails = [row[1] for row in rows]
    assert "Jordan Reyes" in names
    assert all("@" in email for email in emails)
    assert len(set(emails)) == 4


def test_try_resume_extract_text_reads_plain_text() -> None:
    try_resume = _load_script("try_resume")
    text = try_resume.extract_text(SAMPLES_DIR / "strong_backend.txt")
    assert "Jordan Reyes" in text


def test_try_resume_run_returns_analysis_without_saving(session: Session) -> None:
    try_resume = _load_script("try_resume")

    tenant = Tenant(name="Try Co")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    assert tenant.id is not None
    job = _make_job(session, tenant.id)

    candidate = Candidate(
        tenant_id=tenant.id,
        full_name="Jordan Reyes",
        email="jordan.reyes@example.com",
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)

    audit_before = len(session.exec(select(AuditLog)).all())

    result = try_resume.run(session, SAMPLES_DIR / "strong_backend.txt", job.id)

    assert "analysis" in result
    assert "score" in result and "breakdown" in result
    assert result["model"] == "fake"
    assert result["analysis"]["candidate"]["full_name"] == "Jordan Reyes"

    # Nothing was written: no audit rows, the job keeps its empty requirements
    # and the candidate's resume_text is untouched.
    assert len(session.exec(select(AuditLog)).all()) == audit_before
    session.refresh(job)
    assert job.must_have_skills == []
    assert job.nice_to_have_skills == []
    assert job.min_years_experience is None
    session.refresh(candidate)
    assert candidate.resume_text is None


def test_seed_sample_candidates_creates_candidates_and_applications(
    session: Session,
) -> None:
    seed = _load_script("seed")

    tenant = Tenant(name="Seed Co")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    assert tenant.id is not None
    job = _make_job(session, tenant.id)

    candidates = seed.seed_sample_candidates(
        session, tenant_id=tenant.id, job_id=job.id
    )
    session.commit()

    assert len(candidates) == 4
    stored = session.exec(
        select(Candidate).where(Candidate.tenant_id == tenant.id)
    ).all()
    assert len(stored) == 4
    assert {c.full_name for c in stored} == {
        "Jordan Reyes",
        "Priya Nair",
        "Marco Bianchi",
        "Dana Whitfield",
    }
    assert all(c.resume_text for c in stored)

    apps = session.exec(
        select(Application).where(Application.job_id == job.id)
    ).all()
    assert len(apps) == 4
    assert {a.candidate_id for a in apps} == {c.id for c in stored}


# --- dedupe_jobs.py (TASK 4) ----------------------------------------------


def _dedupe_tenant(session: Session) -> Tenant:
    tenant = Tenant(name="Dedupe Co")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    assert tenant.id is not None
    return tenant


def test_dedupe_find_duplicate_groups_groups_by_normalized_title(
    session: Session,
) -> None:
    dedupe = _load_script("dedupe_jobs")
    tenant = _dedupe_tenant(session)

    older = Job(tenant_id=tenant.id, title="Mobile App Developer", description="a")
    newer = Job(tenant_id=tenant.id, title="mobile  app   developer", description="b")
    other = Job(tenant_id=tenant.id, title="Backend Engineer", description="c")
    session.add(older)
    session.add(newer)
    session.add(other)
    session.commit()

    groups = dedupe.find_duplicate_groups(session)
    assert len(groups) == 1
    assert {job.id for job in groups[0]} == {older.id, newer.id}


def test_dedupe_merge_group_moves_children_to_oldest_job(session: Session) -> None:
    dedupe = _load_script("dedupe_jobs")
    tenant = _dedupe_tenant(session)

    user = User(
        tenant_id=tenant.id,
        email="admin@merge.com",
        hashed_password="not-a-real-hash",
        role=UserRole.ADMIN,
    )
    candidate = Candidate(
        tenant_id=tenant.id, full_name="Ada Lovelace", email="ada@merge.com"
    )
    session.add(user)
    session.add(candidate)
    session.commit()
    session.refresh(user)
    session.refresh(candidate)

    keeper = Job(
        tenant_id=tenant.id,
        title="Mobile App Developer",
        description="keep",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    duplicate = Job(
        tenant_id=tenant.id,
        title="mobile app developer",
        description="duplicate",
        must_have_skills=["Kotlin"],
        min_years_experience=3.0,
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    session.add(keeper)
    session.add(duplicate)
    session.commit()
    session.refresh(keeper)
    session.refresh(duplicate)
    assert keeper.id is not None and duplicate.id is not None

    application = Application(
        tenant_id=tenant.id, candidate_id=candidate.id, job_id=duplicate.id
    )
    approval = Approval(
        tenant_id=tenant.id,
        action_type=ApprovalActionType.SHORTLIST,
        target_type="job",
        target_id=duplicate.id,
        requested_by=user.id,
    )
    session.add(application)
    session.add(approval)
    session.commit()
    session.refresh(application)
    session.refresh(approval)

    # Passing the group out of order must still pick the oldest job as keeper.
    actions = dedupe.merge_group(session, [duplicate, keeper], apply=True)

    assert len(actions) == 1
    session.refresh(application)
    session.refresh(approval)
    assert application.job_id == keeper.id
    assert approval.target_id == keeper.id
    assert session.get(Job, duplicate.id) is None
    session.refresh(keeper)
    assert keeper.must_have_skills == ["Kotlin"]
    assert keeper.min_years_experience == 3.0


def test_dedupe_main_dry_run_reports_without_changing(
    session: Session,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    dedupe = _load_script("dedupe_jobs")
    tenant = _dedupe_tenant(session)

    session.add(Job(tenant_id=tenant.id, title="Mobile App Developer", description="a"))
    session.add(Job(tenant_id=tenant.id, title="mobile app developer", description="b"))
    session.commit()

    monkeypatch.setattr(dedupe, "engine", session.get_bind())
    exit_code = dedupe.main(apply=False)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "duplicate title group" in output
    assert "Dry run" in output
    assert len(session.exec(select(Job)).all()) == 2
