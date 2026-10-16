from datetime import datetime
from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    title: str
    description: str
    status: str = "open"
    must_have_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    min_years_experience: float | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    must_have_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    min_years_experience: float | None = None
    created_at: datetime
