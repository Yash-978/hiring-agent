from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class ApplicationCreate(BaseModel):
    candidate_id: int
    job_id: int


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    job_id: int
    candidate_name: str
    job_title: str
    status: str
    score: float | None = None
    score_reasoning: str | None = None
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_type: str
    actor_name: str
    action: str
    entity_type: str
    entity_id: int
    details: dict[str, Any] | None = None
    created_at: datetime
