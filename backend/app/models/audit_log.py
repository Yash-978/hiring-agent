from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import Column, JSON, String
from sqlmodel import Field, SQLModel


class AuditActorType(str, Enum):
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class AuditLog(SQLModel, table=True):
    __tablename__ = "auditlog"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    actor_type: AuditActorType = Field(
        sa_column=Column(String, nullable=False)
    )
    actor_name: str
    action: str
    entity_type: str
    entity_id: int
    details: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
