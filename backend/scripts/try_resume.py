#!/usr/bin/env python3
"""Try the resume analysis agent against a resume file and a job.

This is a read-only developer tool: it loads a resume from disk, runs the same
analysis the API runs, prints the result as JSON and writes nothing to the
database, storage or audit log.

Usage:
    python scripts/try_resume.py samples/resumes/strong_backend.txt 1
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, create_engine

from app.agents import (
    LLMError,
    analyze_resume,
    extract_job_requirements,
    get_llm_client,
)
from app.models import Job


def extract_text(path: Path) -> str:
    """Return resume text: PDFs are extracted, everything else is read as text."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="replace")


def run(session: Session, resume_path: Path, job_id: int) -> dict:
    """Analyze a resume for a job and return the result dict, writing nothing."""
    job = session.get(Job, job_id)
    if job is None:
        raise SystemExit(f"Job {job_id} not found")

    resume_text = extract_text(resume_path)
    client = get_llm_client()

    must_have_skills = job.must_have_skills
    nice_to_have_skills = job.nice_to_have_skills
    min_years_experience = job.min_years_experience

    # Mirror the API's "extract when the job is empty" step, but keep the
    # extracted requirements in memory only. Nothing is saved.
    if (
        not must_have_skills
        and not nice_to_have_skills
        and min_years_experience is None
    ):
        requirements = extract_job_requirements(client, job.description)
        must_have_skills = requirements.must_have_skills
        nice_to_have_skills = requirements.nice_to_have_skills
        min_years_experience = requirements.min_years_experience

    result = analyze_resume(
        client=client,
        resume_text=resume_text,
        job_description=job.description,
        must_have_skills=must_have_skills,
        nice_to_have_skills=nice_to_have_skills,
        min_years_experience=min_years_experience,
    )
    return result.model_dump()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a resume without saving.")
    parser.add_argument("resume", type=Path, help="Path to the resume file")
    parser.add_argument("job_id", type=int, help="Id of the job to analyze against")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "sqlite:///demo.db"),
        help="Database URL (defaults to $DATABASE_URL)",
    )
    args = parser.parse_args(argv)

    if not args.resume.is_file():
        print(f"Resume file not found: {args.resume}", file=sys.stderr)
        return 1

    engine = create_engine(args.database_url)
    try:
        with Session(engine) as session:
            result = run(session, args.resume, args.job_id)
    except LLMError as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    print("\n(nothing was saved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
