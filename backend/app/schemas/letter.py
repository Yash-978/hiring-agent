from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class OfferDraftRequest(BaseModel):
    salary: float
    currency: str
    start_date: date


class LetterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    application_id: int
    approval_id: int | None = None
    content: str | None = None
    file_path: str | None = None
    created_at: datetime