from datetime import datetime
from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    title: str
    description: str
    status: str = "open"
    must_have_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    min_years_experience: float | None = None


class CompareJobRead(BaseModel):
    id: int
    title: str
    must_have_skills: list[str] = []
    nice_to_have_skills: list[str] = []


class CompareCriterionRead(BaseModel):
    criterion: str
    kind: str
    verdict: str


class CompareCandidateRead(BaseModel):
    application_id: int
    name: str
    score: float | None
    recommendation: str
    confidence: str
    years: float | None = None
    breakdown: dict[str, float]
    criteria: list[CompareCriterionRead]


class JobCompareRead(BaseModel):
    job: CompareJobRead
    candidates: list[CompareCandidateRead]


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
