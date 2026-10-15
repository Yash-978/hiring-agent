from datetime import datetime
from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    title: str
    description: str
    status: str = "open"


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    created_at: datetime
