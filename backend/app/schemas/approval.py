from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApprovalDecisionRequest(BaseModel):
    note: str | None = None


class ApprovalRejectRequest(BaseModel):
    """Rejecting an approval requires a meaningful note of at least 3 characters."""

    note: str = Field(min_length=3)

    @field_validator("note")
    @classmethod
    def _note_is_meaningful(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("note must be at least 3 characters")
        return cleaned


class ApprovalCountsRead(BaseModel):
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    action_type: str
    target_type: str
    target_id: int
    application_id: int | None = None
    candidate_name: str | None = None
    job_title: str | None = None
    score: float | None = None
    recommendation: str | None = None
    requested_by_name: str | None = None
    payload: dict[str, Any] | None = None
    status: str
    requested_by: int
    decided_by_user_id: int | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    created_at: datetime
