from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import Column, JSON, String
from sqlmodel import Field, SQLModel


class ApplicationStatus(str, Enum):
    NEW = "new"
    ANALYZED = "analyzed"
    SHORTLIST_APPROVED = "shortlist_approved"
    SHORTLIST_REJECTED = "shortlist_rejected"
    OFFER_DRAFTED = "offer_drafted"
    OFFER_APPROVED = "offer_approved"
    OFFER_REJECTED = "offer_rejected"


class Application(SQLModel, table=True):
    __tablename__ = "application"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    candidate_id: int = Field(foreign_key="candidate.id", index=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    status: ApplicationStatus = Field(
        default=ApplicationStatus.NEW,
        sa_column=Column(String, nullable=False, default=ApplicationStatus.NEW.value),
    )
    score: float | None = Field(default=None)
    score_reasoning: str | None = Field(default=None)
    # Full resume analysis bundle (analysis, score, breakdown, flags, model,
    # prompt_version) and the stored upload path relative to STORAGE_DIR.
    analysis: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    resume_path: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
