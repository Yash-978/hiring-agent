from datetime import datetime
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
