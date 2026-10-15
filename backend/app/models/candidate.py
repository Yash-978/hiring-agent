from datetime import datetime, timezone
from typing import Any
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Candidate(SQLModel, table=True):
    __tablename__ = "candidate"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    full_name: str
    email: str
    resume_text: str | None = Field(default=None)
    parsed_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
