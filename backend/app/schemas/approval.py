from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class ApprovalDecisionRequest(BaseModel):
    note: str | None = None


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    action_type: str
    target_type: str
    target_id: int
    candidate_name: str | None = None
    job_title: str | None = None
    payload: dict[str, Any] | None = None
    status: str
    requested_by: int
    decided_by_user_id: int | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    created_at: datetime
