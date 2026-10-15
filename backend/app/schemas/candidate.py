from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class CandidateCreate(BaseModel):
    full_name: str
    email: str
    resume_text: str | None = None
    parsed_data: dict[str, Any] | None = None


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    resume_text: str | None = None
    parsed_data: dict[str, Any] | None = None
    created_at: datetime
