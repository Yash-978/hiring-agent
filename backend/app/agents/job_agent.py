"""Job requirements extraction agent.

Extracts the must-have skills, nice-to-have skills and minimum years of
experience from a free-text job description so an empty Job can be populated
automatically when a resume is analyzed.
"""

from pydantic import BaseModel, Field

from app.agents.llm import LLMClient


class JobRequirements(BaseModel):
    """Structured requirements extracted from a job description."""

    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    min_years_experience: float | None = None


SYSTEM_PROMPT = (
    "You extract the hiring requirements from a job description. "
    "Return only requirements that are clearly stated in the description. "
    "must_have_skills are the required skills, nice_to_have_skills are the "
    "optional or preferred skills, and min_years_experience is the minimum "
    "number of years of relevant experience (null when not stated). "
    "Do not invent requirements that are not present in the text."
)


def extract_job_requirements(
    client: LLMClient,
    job_description: str,
) -> JobRequirements:
    """Extract structured hiring requirements from a job description."""
    prompt = (
        f"Job Description:\n{job_description}\n\n"
        "Return the requirements in the required JSON format."
    )
    return client.generate_json(SYSTEM_PROMPT, prompt, JobRequirements)
