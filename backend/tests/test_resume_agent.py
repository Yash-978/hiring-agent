"""Tests for the resume analysis agent (app.agents.resume_agent).

These tests pin the two honesty rules added on top of the LLM judgement:
  1. a job with too few structured must-have skills is never scored (null), and
  2. experience is computed in code from the resume years and the job minimum,
     so a strong-looking resume, an average one and an unrelated one produce a
     strictly decreasing score.

The stub LLM below is local to this file so the tests do not depend on the
shared fake client; it judges a skill as met when the skill token appears in
the resume and takes the candidate's years from its constructor.
"""

from app.agents.llm import LLMClient
from app.agents.resume_agent import (
    MIN_MUST_HAVE,
    CandidateInfo,
    CriterionAssessment,
    ResumeAnalysis,
    analyze_resume,
)

MUST_HAVES = ["Python", "FastAPI", "PostgreSQL"]
NICE_TO_HAVES = ["Docker", "AWS"]
MIN_YEARS = 3.0

JOB_DESCRIPTION = "Build and run the backend platform."


def _skills_from(prompt: str, label: str) -> list[str]:
    for line in prompt.splitlines():
        if line.startswith(label):
            return [s.strip() for s in line[len(label):].split(",") if s.strip()]
    return []


class _StubLLM(LLMClient):
    """Judges each required skill by presence in the resume."""

    model_name = "stub"

    def __init__(self, years: float | None) -> None:
        self.years = years

    def generate_json(self, system: str, prompt: str, schema: type) -> ResumeAnalysis:
        resume = prompt.split("<<<RESUME>>>")[1].split("<<<END_RESUME>>>")[0].lower()
        criteria: list[CriterionAssessment] = []
        for skill in _skills_from(prompt, "Must-have skills: "):
            present = skill.lower() in resume
            criteria.append(
                CriterionAssessment(
                    criterion=skill,
                    kind="must_have",
                    verdict="met" if present else "not_met",
                    evidence=skill if present else "none",
                )
            )
        for skill in _skills_from(prompt, "Nice-to-have skills: "):
            present = skill.lower() in resume
            criteria.append(
                CriterionAssessment(
                    criterion=skill,
                    kind="nice_to_have",
                    verdict="met" if present else "not_met",
                    evidence=skill if present else "none",
                )
            )
        return ResumeAnalysis(
            candidate=CandidateInfo(full_name="Casey", total_years_experience=self.years),
            criteria=criteria,
            recommendation="shortlist",
            confidence="medium",
        )


def _analyze(resume: str, years: float | None):
    return analyze_resume(
        client=_StubLLM(years),
        resume_text=resume,
        job_description=JOB_DESCRIPTION,
        must_have_skills=MUST_HAVES,
        nice_to_have_skills=NICE_TO_HAVES,
        min_years_experience=MIN_YEARS,
    )


# ---------------------------------------------------------------------------
# three synthetic resumes: strong > average > unrelated
# ---------------------------------------------------------------------------


def test_strong_resume_scores_full_marks() -> None:
    resume = "Python, FastAPI, PostgreSQL, Docker and AWS across 5 years of work."
    result = _analyze(resume, years=5.0)
    assert result.score == 100.0
    assert result.breakdown["must_have"]["ratio"] == 1.0
    assert result.breakdown["experience"]["ratio"] == 1.0


def test_average_resume_scores_in_between() -> None:
    resume = "Python and FastAPI, some Docker, 1.5 years so far."
    result = _analyze(resume, years=1.5)
    # must_have 2/3, nice_to_have 1/2, experience 1.5/3
    # 0.6667*0.70 + 0.5*0.20 + 0.5*0.10 = 0.6167 -> 61.7
    assert result.score == 61.7


def test_unrelated_resume_scores_zero() -> None:
    resume = "I paint houses and manage a small shop."
    result = _analyze(resume, years=0.0)
    assert result.score == 0.0


def test_scores_strictly_decrease_from_strong_to_unrelated() -> None:
    strong = _analyze(
        "Python, FastAPI, PostgreSQL, Docker, AWS, 5 years.", years=5.0
    )
    average = _analyze("Python, FastAPI, Docker, 1.5 years.", years=1.5)
    unrelated = _analyze("I paint houses.", years=0.0)
    assert strong.score is not None and average.score is not None
    assert unrelated.score is not None
    assert strong.score > average.score > unrelated.score


def test_unknown_years_never_earn_experience_credit() -> None:
    resume = "Python, FastAPI, PostgreSQL, Docker, AWS."
    result = _analyze(resume, years=None)
    # Skills are perfect but the resume never states years, so experience is 0.
    # 0.70 + 0.20 + 0 = 0.90 -> 90.0
    assert result.score == 90.0
    assert result.breakdown["experience"]["ratio"] == 0.0


# ---------------------------------------------------------------------------
# the insufficient-requirements gate
# ---------------------------------------------------------------------------


def test_too_few_must_haves_leaves_the_score_null() -> None:
    result = analyze_resume(
        client=_StubLLM(years=10.0),
        resume_text="Python and FastAPI, 10 years.",
        job_description=JOB_DESCRIPTION,
        must_have_skills=["Python", "FastAPI"],  # one short of the floor
        nice_to_have_skills=NICE_TO_HAVES,
        min_years_experience=MIN_YEARS,
    )
    assert result.score is None
    assert result.breakdown == {}
    assert "insufficient_job_requirements" in result.flags
    assert result.analysis.recommendation == "needs_more_info"


def test_missing_must_haves_entirely_leaves_the_score_null() -> None:
    result = analyze_resume(
        client=_StubLLM(years=10.0),
        resume_text="Python and FastAPI, 10 years.",
        job_description=JOB_DESCRIPTION,
        min_years_experience=MIN_YEARS,
    )
    assert result.score is None
    assert "insufficient_job_requirements" in result.flags


def test_exactly_the_floor_is_scored() -> None:
    result = _analyze("Python, FastAPI, PostgreSQL, 5 years.", years=5.0)
    assert MIN_MUST_HAVE == 3
    assert result.score is not None
    assert "insufficient_job_requirements" not in result.flags
