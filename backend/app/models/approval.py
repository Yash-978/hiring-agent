from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import Column, JSON, String
from sqlmodel import Field, SQLModel


class ApprovalActionType(str, Enum):
    SHORTLIST = "shortlist"
    OFFER_LETTER = "offer_letter"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Approval(SQLModel, table=True):
    __tablename__ = "approval"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    action_type: ApprovalActionType = Field(
        sa_column=Column(String, nullable=False)
    )
    target_type: str
    target_id: int
    payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        sa_column=Column(String, nullable=False, default=ApprovalStatus.PENDING.value),
    )
    requested_by: int = Field(foreign_key="user.id", index=True)
    decided_by_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    decided_at: datetime | None = Field(default=None)
    decision_note: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
