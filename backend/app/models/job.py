from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class Job(SQLModel, table=True):
    __tablename__ = "job"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    title: str
    description: str
    status: JobStatus = Field(
        default=JobStatus.OPEN,
        sa_column=Column(String, nullable=False, default=JobStatus.OPEN.value),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
