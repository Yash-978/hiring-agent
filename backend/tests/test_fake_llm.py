"""Tests for the deterministic fake LLM client (app.agents.llm).

The fake client is the offline demo judge: it reads the structured
requirements and the resume text out of the analysis prompt and judges each
skill by looking for it in the resume. These tests pin that behaviour so the
demo mode stays honest and the shared fake used by the API tests keeps
exercising the real scoring path.
"""

from app.agents.llm import FakeLLMClient
from app.agents.resume_agent import ResumeAnalysisResult, analyze_resume

# Jordan evidences Python/FastAPI in prose, but lists PostgreSQL only in a
# bare skills line, and never mentions Kubernetes at all.
RESUME = (
    "Jordan Reyes\n"
    "Email: jordan@example.com\n"
    "Backend engineer with 7 years of experience building APIs.\n"
    "Built services with Python and FastAPI.\n"
    "Skills: PostgreSQL, Redis\n"
)


def _analyze(
    resume: str,
    must_have: list[str],
    nice_to_have: list[str] | None = None,
) -> ResumeAnalysisResult:
    return analyze_resume(
        client=FakeLLMClient(),
        resume_text=resume,
        job_description="Backend platform role.",
        must_have_skills=must_have,
        nice_to_have_skills=nice_to_have or [],
        min_years_experience=3.0,
    )


def _by_criterion(result: ResumeAnalysisResult) -> dict[str, object]:
    return {c.criterion: c for c in result.analysis.criteria}


def test_fake_judge_reads_prose_skills_as_met() -> None:
    result = _analyze(RESUME, ["Python", "FastAPI", "PostgreSQL"])
    criteria = _by_criterion(result)

    python = criteria["Python"]
    assert python.verdict == "met"
    assert python.evidence_verified is True

    fastapi = criteria["FastAPI"]
    assert fastapi.verdict == "met"
    assert fastapi.evidence_verified is True


def test_fake_judge_treats_a_skills_list_as_partial() -> None:
    result = _analyze(RESUME, ["Python", "FastAPI", "PostgreSQL"])
    postgres = _by_criterion(result)["PostgreSQL"]

    assert postgres.verdict == "partial"
    assert postgres.evidence_verified is True


def test_fake_judge_marks_an_absent_skill_not_met() -> None:
    result = _analyze(RESUME, ["Python", "FastAPI", "Kubernetes"])
    kubernetes = _by_criterion(result)["Kubernetes"]

    assert kubernetes.verdict == "not_met"
    assert kubernetes.evidence == "none"
    assert kubernetes.evidence_verified is False


def test_fake_judge_extracts_candidate_details() -> None:
    result = _analyze(RESUME, ["Python", "FastAPI", "PostgreSQL"])
    candidate = result.analysis.candidate

    assert candidate.full_name == "Jordan Reyes"
    assert candidate.email == "jordan@example.com"
    assert candidate.total_years_experience == 7.0


def test_fake_judge_shortlists_when_every_requirement_is_met() -> None:
    resume = (
        "Priya Nair\n"
        "Email: priya@example.com\n"
        "Engineer with 5 years of experience.\n"
        "Delivered Python and FastAPI services backed by PostgreSQL.\n"
    )
    result = _analyze(resume, ["Python", "FastAPI", "PostgreSQL"])

    assert result.analysis.recommendation == "shortlist"
    assert result.analysis.confidence == "high"
    assert result.score == 100.0


def test_fake_judge_rejects_when_no_requirement_is_met() -> None:
    result = _analyze(
        "Dana Whitfield\nRuns a small shop and paints houses.",
        ["Python", "FastAPI", "PostgreSQL"],
    )

    assert result.analysis.recommendation == "reject"
    assert result.score == 0.0
