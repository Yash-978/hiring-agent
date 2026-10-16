#!/usr/bin/env python3
"""Seed script to create demo tenant, admin user, job, and candidates."""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, create_engine, SQLModel
from app.db import create_db_and_tables
from app.models import Tenant, User, UserRole, Job, Candidate, Application, ApplicationStatus
from app.services.auth_service import hash_password
from app.services.job_service import normalize_title

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "resumes"

# One demo job per category, each with explicit requirements so the scoring gate
# and the hard-gap caps have something real to judge against. The "samples" key
# names the resume files (without .txt) that belong to that job.
DEMO_JOBS: list[dict[str, Any]] = [
    {
        "title": "Senior Backend Engineer",
        "description": (
            "We are looking for a Senior Backend Engineer with strong Python skills. "
            "You will own services end to end, from schema design to on-call. "
            "Required: Python, FastAPI, PostgreSQL. "
            "Nice to have: Redis, Celery, Docker, Kubernetes."
        ),
        "must_have_skills": ["Python", "FastAPI", "PostgreSQL"],
        "nice_to_have_skills": ["Redis", "Celery", "Docker", "Kubernetes"],
        "min_years_experience": 5.0,
        "samples": ["strong_backend", "average_backend"],
    },
    {
        "title": "Mobile App Developer",
        "description": (
            "We are hiring a Mobile App Developer to build our first mobile client. "
            "You will ship features in React Native against our REST APIs. "
            "Required: React Native, TypeScript, REST APIs. "
            "Nice to have: Swift, Kotlin, Firebase."
        ),
        "must_have_skills": ["React Native", "TypeScript", "REST APIs"],
        "nice_to_have_skills": ["Swift", "Kotlin", "Firebase"],
        "min_years_experience": 3.0,
        "samples": ["frontend_only", "non_technical"],
    },
]


def read_sample_resume_entries(
    samples_dir: Path | None = None,
) -> list[tuple[str, str, str, str]]:
    """Return (stem, full_name, email, resume_text) for each sample resume file."""
    directory = samples_dir if samples_dir is not None else SAMPLES_DIR
    entries: list[tuple[str, str, str, str]] = []
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        full_name = lines[0] if lines else path.stem.replace("_", " ").title()
        email = next(
            (token.strip(".,;:()<>") for token in text.split() if "@" in token and "." in token),
            f"{path.stem}@example.com",
        )
        entries.append((path.stem, full_name, email, text))
    return entries


def read_sample_resumes(samples_dir: Path | None = None) -> list[tuple[str, str, str]]:
    """Return (full_name, email, resume_text) for each sample resume file."""
    return [
        (full_name, email, resume_text)
        for _stem, full_name, email, resume_text in read_sample_resume_entries(samples_dir)
    ]


def _attach_sample(
    session: Session,
    tenant_id: int,
    job_id: int,
    full_name: str,
    email: str,
    resume_text: str,
) -> Candidate:
    """Create a candidate from a sample resume and apply them to a job."""
    candidate = Candidate(
        tenant_id=tenant_id,
        full_name=full_name,
        email=email,
        resume_text=resume_text,
    )
    session.add(candidate)
    session.flush()
    assert candidate.id is not None
    session.add(
        Application(
            tenant_id=tenant_id,
            candidate_id=candidate.id,
            job_id=job_id,
            status=ApplicationStatus.NEW,
        )
    )
    return candidate


def seed_sample_candidates(
    session: Session, tenant_id: int, job_id: int
) -> list[Candidate]:
    """Load the sample resumes from disk as candidates for one demo job."""
    return [
        _attach_sample(session, tenant_id, job_id, full_name, email, resume_text)
        for full_name, email, resume_text in read_sample_resumes()
    ]


def seed_demo_jobs(
    session: Session, tenant_id: int
) -> list[tuple[Job, list[Candidate]]]:
    """Create one demo job per category and attach the matching sample resumes."""
    entries = {
        stem: (full_name, email, resume_text)
        for stem, full_name, email, resume_text in read_sample_resume_entries()
    }

    seeded: list[tuple[Job, list[Candidate]]] = []
    for spec in DEMO_JOBS:
        job = Job(
            tenant_id=tenant_id,
            title=spec["title"],
            title_key=normalize_title(spec["title"]),
            description=spec["description"],
            must_have_skills=list(spec["must_have_skills"]),
            nice_to_have_skills=list(spec["nice_to_have_skills"]),
            min_years_experience=spec["min_years_experience"],
        )
        session.add(job)
        session.flush()
        assert job.id is not None

        candidates = [
            _attach_sample(session, tenant_id, job.id, *entries[stem])
            for stem in spec["samples"]
        ]
        seeded.append((job, candidates))
    return seeded


def main(with_samples: bool = False) -> None:
    """Seed the demo tenant with one job per category and its sample candidates.

    ``with_samples`` is kept for backwards compatibility: the sample resumes are
    always seeded now, because they are what makes the demo meaningful.
    """
    database_url = os.getenv("DATABASE_URL", "sqlite:///demo.db")
    seed_password = os.getenv("SEED_PASSWORD", "demo123")

    engine = create_engine(database_url)
    # Create tables
    SQLModel.metadata.create_all(engine)
    # Or use the app's create_db_and_tables which does the same
    # create_db_and_tables()

    with Session(engine) as session:
        # Create demo tenant
        tenant = Tenant(name="Demo Co")
        session.add(tenant)
        session.flush()
        assert tenant.id is not None

        # Create admin user
        user = User(
            tenant_id=tenant.id,
            email="admin@demo.test",
            hashed_password=hash_password(seed_password),
            role=UserRole.ADMIN,
        )
        session.add(user)
        session.flush()
        assert user.id is not None

        # One job per category, each with explicit requirements, and the sample
        # resumes attached to the job they belong to.
        seeded = seed_demo_jobs(session, tenant_id=tenant.id)
        session.commit()

        print(f"[OK] Created tenant: {tenant.name} (id={tenant.id})")
        print(f"[OK] Created admin user: {user.email} (id={user.id})")
        for job, candidates in seeded:
            print(
                f"[OK] Created job: {job.title} (id={job.id}, "
                f"must-have={job.must_have_skills}, "
                f"nice-to-have={job.nice_to_have_skills}, "
                f"min_years={job.min_years_experience})"
            )
            for candidate in candidates:
                print(
                    f"[OK] Created candidate: {candidate.full_name} "
                    f"({candidate.email}, id={candidate.id}) -> {job.title}"
                )
        print(f"\nDemo data seeded successfully!")
        print(f"Login with: admin@demo.test / {seed_password}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo data.")
    parser.add_argument(
        "--with-samples",
        action="store_true",
        help=(
            "Deprecated: the sample resumes are always loaded as candidates for "
            "the matching demo job."
        ),
    )
    args = parser.parse_args()
    main(with_samples=args.with_samples)