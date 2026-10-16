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


class AnalysisJobRef(BaseModel):
    id: int
    title: str


class AnalysisCandidateRead(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    current_title: str | None = None
    total_years_experience: float | None = None
    education: list[str] = []
    skills: list[str] = []


class AnalysisCriterionRead(BaseModel):
    criterion: str
    kind: str
    verdict: str
    evidence: str
    evidence_verified: bool = False
    note: str = ""


class AnalysisBreakdownEntry(BaseModel):
    ratio: float
    weight: float
    count: int


class ApplicationAnalysisRead(BaseModel):
    application_id: int
    job: AnalysisJobRef
    candidate: AnalysisCandidateRead
    criteria: list[AnalysisCriterionRead]
    score: float
    breakdown: dict[str, AnalysisBreakdownEntry]
    strengths: list[str]
    concerns: list[str]
    questions_for_candidate: list[str]
    recommendation: str
    confidence: str
    flags: list[str]
    model: str
    prompt_version: str
    resume_available: bool


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
