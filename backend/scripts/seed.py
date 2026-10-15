#!/usr/bin/env python3
"""Seed script to create demo tenant, admin user, job, and candidates."""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, create_engine, SQLModel
from app.db import create_db_and_tables
from app.models import Tenant, User, UserRole, Job, Candidate, Application, ApplicationStatus
from app.services.auth_service import hash_password


def main() -> None:
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

        # Create job
        job = Job(
            tenant_id=tenant.id,
            title="Senior Backend Engineer",
            description=(
                "We are looking for a Senior Backend Engineer with strong Python skills. "
                "You will work on our hiring platform, building APIs, integrating with AI agents, "
                "and ensuring data integrity across the hiring pipeline. "
                "Required: Python, FastAPI, PostgreSQL, SQLAlchemy. "
                "Nice to have: Redis, Celery, Docker, Kubernetes."
            ),
        )
        session.add(job)
        session.flush()
        assert job.id is not None

        # Create candidates
        cand1 = Candidate(
            tenant_id=tenant.id,
            full_name="Alice Smith",
            email="alice.smith@example.com",
            resume_text=(
                "Alice Smith\n"
                "Senior Python Developer with 7 years experience.\n"
                "Skills: Python, FastAPI, PostgreSQL, SQLAlchemy, Redis, Docker, Kubernetes.\n"
                "Experience: Built scalable APIs, microservices, and data pipelines.\n"
                "Education: BS Computer Science, Stanford University."
            ),
        )
        session.add(cand1)

        cand2 = Candidate(
            tenant_id=tenant.id,
            full_name="Bob Johnson",
            email="bob.johnson@example.com",
            resume_text=(
                "Bob Johnson\n"
                "Backend Engineer with 4 years experience.\n"
                "Skills: Python, Django, PostgreSQL, REST APIs, Git, CI/CD.\n"
                "Experience: Developed web applications and internal tools.\n"
                "Education: MS Software Engineering, MIT."
            ),
        )
        session.add(cand2)
        session.flush()
        assert cand1.id is not None
        assert cand2.id is not None

        # Create applications
        app1 = Application(
            tenant_id=tenant.id,
            candidate_id=cand1.id,
            job_id=job.id,
            status=ApplicationStatus.NEW,
        )
        session.add(app1)

        app2 = Application(
            tenant_id=tenant.id,
            candidate_id=cand2.id,
            job_id=job.id,
            status=ApplicationStatus.NEW,
        )
        session.add(app2)

        session.commit()

        print(f"✓ Created tenant: {tenant.name} (id={tenant.id})")
        print(f"✓ Created admin user: {user.email} (id={user.id})")
        print(f"✓ Created job: {job.title} (id={job.id})")
        print(f"✓ Created candidate: {cand1.full_name} (id={cand1.id})")
        print(f"✓ Created candidate: {cand2.full_name} (id={cand2.id})")
        print(f"✓ Created application for {cand1.full_name}")
        print(f"✓ Created application for {cand2.full_name}")
        print(f"\nDemo data seeded successfully!")
        print(f"Login with: admin@demo.test / {seed_password}")


if __name__ == "__main__":
    main()