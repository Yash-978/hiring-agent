"""Agents package."""

from app.agents.llm import (
    LLMClient,
    FakeLLMClient,
    GeminiLLMClient,
    get_llm_client,
    LLMError,
)
from app.agents.job_agent import JobRequirements, extract_job_requirements
from app.agents.resume_agent import ResumeAnalysis, analyze_resume
from app.agents.offer_agent import OfferDraft, draft_offer

__all__ = [
    "LLMClient",
    "FakeLLMClient",
    "GeminiLLMClient",
    "get_llm_client",
    "LLMError",
    "JobRequirements",
    "extract_job_requirements",
    "ResumeAnalysis",
    "analyze_resume",
    "OfferDraft",
    "draft_offer",
]
