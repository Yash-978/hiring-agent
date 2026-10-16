#!/usr/bin/env python3
"""Merge duplicate jobs (same tenant, same normalized title) into the oldest job.

Duplicate titles cannot be indexed uniquely, so `ensure_job_unique_index` skips
the index and logs a warning when duplicates exist. Run this script to clean up,
then restart the API so the unique index can be created.

Usage:
    python -m scripts.dedupe_jobs            # dry run: report only
    python -m scripts.dedupe_jobs --apply    # merge (asks for confirmation)
    python -m scripts.dedupe_jobs --apply --yes   # merge without prompting

For each duplicate group the oldest job (earliest created_at, then lowest id) is
kept. Applications and job-targeted approvals are moved onto the kept job, its
empty requirements are filled from a duplicate, and the duplicates are deleted.
"""

import argparse
import sys
from pathlib import Path

# Add backend to path so `app` imports resolve when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.db import engine
from app.models import Application, Approval, Job
from app.services.job_service import normalize_title


def find_duplicate_groups(session: Session) -> list[list[Job]]:
    """Return groups of jobs that share a tenant and a normalized title."""
    jobs = list(session.exec(select(Job)).all())
    by_key: dict[tuple[int, str], list[Job]] = {}
    for job in jobs:
        by_key.setdefault((job.tenant_id, normalize_title(job.title)), []).append(job)
    return [group for group in by_key.values() if len(group) > 1]


def _ordered(group: list[Job]) -> list[Job]:
    """Oldest first: by created_at, then by id."""
    return sorted(group, key=lambda job: (job.created_at, job.id or 0))


def merge_group(session: Session, group: list[Job], apply: bool = False) -> list[str]:
    """Merge duplicates in `group` into the oldest job. Returns action descriptions."""
    ordered = _ordered(group)
    keeper = ordered[0]
    assert keeper.id is not None
    actions: list[str] = []

    for duplicate in ordered[1:]:
        assert duplicate.id is not None
        moved_apps = 0
        for application in session.exec(
            select(Application).where(Application.job_id == duplicate.id)
        ).all():
            application.job_id = keeper.id
            session.add(application)
            moved_apps += 1

        moved_approvals = 0
        for approval in session.exec(
            select(Approval).where(
                Approval.target_type == "job",
                Approval.target_id == duplicate.id,
            )
        ).all():
            approval.target_id = keeper.id
            session.add(approval)
            moved_approvals += 1

        # Keep one requirements set: fill the keeper's gaps from the duplicate.
        if not keeper.must_have_skills and duplicate.must_have_skills:
            keeper.must_have_skills = list(duplicate.must_have_skills)
        if not keeper.nice_to_have_skills and duplicate.nice_to_have_skills:
            keeper.nice_to_have_skills = list(duplicate.nice_to_have_skills)
        if keeper.min_years_experience is None and duplicate.min_years_experience is not None:
            keeper.min_years_experience = duplicate.min_years_experience
        session.add(keeper)

        actions.append(
            f"Merge job {duplicate.id} '{duplicate.title}' into job {keeper.id} "
            f"'{keeper.title}' (moved {moved_apps} application(s), "
            f"{moved_approvals} approval(s))"
        )
        session.delete(duplicate)

    if apply:
        session.commit()
    return actions


def main(apply: bool = False, assume_yes: bool = False) -> int:
    with Session(engine) as session:
        groups = find_duplicate_groups(session)
        if not groups:
            print("No duplicate jobs found.")
            return 0

        print(f"Found {len(groups)} duplicate title group(s):")
        for group in groups:
            ordered = _ordered(group)
            keeper = ordered[0]
            for job in ordered:
                marker = "keep  " if job is keeper else "merge "
                print(f"  {marker} job {job.id}: '{job.title}' (tenant {job.tenant_id})")

        if not apply:
            print("\nDry run. Re-run with --apply to merge the duplicates above.")
            return 0

        if not assume_yes:
            answer = input("Merge these duplicates into the oldest job? [y/N] ")
            if answer.strip().lower() not in ("y", "yes"):
                print("Aborted. Nothing was changed.")
                return 1

        for group in groups:
            for action in merge_group(session, group, apply=True):
                print(f"  [OK] {action}")

        print("\nDone. Restart the API so the unique job title index can be created.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge duplicate jobs by title.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually merge duplicates (default is a dry run).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt (use with --apply).",
    )
    args = parser.parse_args()
    raise SystemExit(main(apply=args.apply, assume_yes=args.yes))
