"""Tests for the developer scripts: try_resume.py and seed.py sample loading."""

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlmodel import Session, select

from app.models import (
    Application,
    AuditLog,
    Candidate,
    Job,
    Tenant,
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
    assert result["analysis"]["candidate"]["full_name"] == "Alice Smith"

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
