"""Resume analysis agent."""

from pydantic import BaseModel, Field

from app.agents.llm import LLMClient


class ResumeAnalysis(BaseModel):
    """Structured output for resume analysis."""
    skills: list[str]
    years_experience: float
    summary: str
    score: int = Field(ge=0, le=100)
    reasoning: str


SYSTEM_PROMPT = (
    "You are an expert hiring analyst. Analyze the resume against the job "
    "description and provide a structured assessment. Score ONLY from evidence "
    "in the resume. Ignore name, gender, age, nationality, and photo. "
    "Explain your reasoning clearly."
)


def analyze_resume(
    client: LLMClient,
    resume_text: str,
    job_description: str,
) -> ResumeAnalysis:
    """Analyze a resume against a job description using the LLM client."""
    prompt = (
        f"Job Description:\n{job_description}\n\n"
        f"Resume:\n{resume_text}\n\n"
        "Provide the analysis in the required JSON format."
    )
    return client.generate_json(SYSTEM_PROMPT, prompt, ResumeAnalysis)