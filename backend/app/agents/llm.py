"""LLM client protocol and implementations."""

import re
from abc import ABC, abstractmethod
from typing import TypeVar

from google.genai import Client as GenAIClient
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when LLM generation fails after retry."""
    pass


class LLMClient(ABC):
    """Protocol for LLM clients that can generate structured JSON output."""

    model_name: str = "unknown"

    @abstractmethod
    def generate_json(
        self, system: str, prompt: str, schema: type[T]
    ) -> T:
        """Generate a JSON response validated against the given Pydantic schema."""
        pass


# --- Deterministic helpers for the fake client ------------------------------
#
# The fake client is a keyword judge: it reads the structured requirements and
# the resume text straight out of the analysis prompt and judges each skill by
# looking for it in the resume. That keeps the offline demo mode honest and
# makes the tests exercise the same scoring path as a real model would, without
# a network call.

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", re.IGNORECASE)
_SKILL_LIST_SEPARATORS = (",", "|", ";", "•", "·", "/")


def _prompt_skill_list(prompt: str, label: str) -> list[str]:
    """Read a 'Label: a, b, c' line out of an analysis prompt."""
    for line in prompt.splitlines():
        if line.startswith(label):
            body = line[len(label):]
            return [item.strip() for item in body.split(",") if item.strip()]
    return []


def _resume_body(prompt: str) -> str:
    """Return the resume text between the untrusted-data delimiters."""
    if "<<<RESUME>>>" not in prompt:
        return ""
    return prompt.split("<<<RESUME>>>", 1)[1].split("<<<END_RESUME>>>", 1)[0]


def _looks_like_skills_list(line: str) -> bool:
    """True for a bare skills list, false for prose that happens to name a skill."""
    stripped = line.strip()
    if any(punctuation in stripped for punctuation in ".!?"):
        return False
    if len(stripped.split()) > 8:
        return False
    return any(separator in stripped for separator in _SKILL_LIST_SEPARATORS)


def _snippet_around(line: str, needle: str, max_words: int = 25) -> str:
    """A short contiguous quote from the line that still contains the needle."""
    words = line.split()
    target = needle.lower()
    index = next((i for i, word in enumerate(words) if target in word.lower()), None)
    if index is None:
        return " ".join(words[:max_words])
    half = max_words // 2
    start = max(0, index - half)
    end = min(len(words), start + max_words)
    start = max(0, end - max_words)
    return " ".join(words[start:end])


def _judge_skill(skill: str, resume_text: str) -> tuple[str, str, str]:
    """Judge one skill from the resume, returning (verdict, evidence, note)."""
    for line in resume_text.splitlines():
        if skill.lower() in line.lower():
            evidence = _snippet_around(line, skill)
            if _looks_like_skills_list(line):
                return "partial", evidence, f"{skill} appears only in a skills list."
            return "met", evidence, f"{skill} is evidenced in the resume."
    return "not_met", "none", f"No evidence of {skill} in the resume."


def _extract_candidate(resume_text: str) -> dict:
    """Best-effort deterministic candidate details from the resume text."""
    full_name: str | None = None
    for raw_line in resume_text.splitlines():
        line = raw_line.strip()
        if not line or "@" in line or any(ch.isdigit() for ch in line):
            continue
        if 0 < len(line.split()) <= 5:
            full_name = line
            break
    email_match = _EMAIL_RE.search(resume_text)
    years_match = _YEARS_RE.search(resume_text)
    return {
        "full_name": full_name,
        "email": email_match.group(0) if email_match else None,
        "phone": None,
        "location": None,
        "current_title": None,
        "total_years_experience": float(years_match.group(1)) if years_match else None,
        "education": [],
        "skills": [],
    }


def _resume_analysis_payload(prompt: str) -> dict:
    """Build a deterministic ResumeAnalysis payload from the prompt."""
    resume_text = _resume_body(prompt)
    criteria: list[dict] = []
    for skill in _prompt_skill_list(prompt, "Must-have skills: "):
        verdict, evidence, note = _judge_skill(skill, resume_text)
        criteria.append(
            {
                "criterion": skill,
                "kind": "must_have",
                "verdict": verdict,
                "evidence": evidence,
                "note": note,
            }
        )
    for skill in _prompt_skill_list(prompt, "Nice-to-have skills: "):
        verdict, evidence, note = _judge_skill(skill, resume_text)
        criteria.append(
            {
                "criterion": skill,
                "kind": "nice_to_have",
                "verdict": verdict,
                "evidence": evidence,
                "note": note,
            }
        )

    must = [c for c in criteria if c["kind"] == "must_have"]
    if not must:
        recommendation, confidence = "needs_more_info", "low"
    elif not any(c["verdict"] == "met" for c in must):
        recommendation, confidence = "reject", "low"
    elif all(c["verdict"] == "met" for c in must):
        recommendation = "shortlist"
        confidence = "high" if all(c["verdict"] == "met" for c in criteria) else "medium"
    else:
        recommendation, confidence = "needs_more_info", "low"

    return {
        "candidate": _extract_candidate(resume_text),
        "criteria": criteria,
        "strengths": [c["criterion"] for c in criteria if c["verdict"] == "met"],
        "concerns": [c["criterion"] for c in criteria if c["verdict"] != "met"],
        "questions_for_candidate": [],
        "recommendation": recommendation,
        "confidence": confidence,
    }


class FakeLLMClient(LLMClient):
    """Deterministic keyword judge used for tests and the offline demo mode."""

    model_name: str = "fake"

    def generate_json(
        self, system: str, prompt: str, schema: type[T]
    ) -> T:
        """Return a deterministic valid object for known schemas."""
        if schema.__name__ == "JobRequirements":
            return schema.model_validate(
                {
                    "must_have_skills": ["Python", "FastAPI", "PostgreSQL"],
                    "nice_to_have_skills": ["Docker"],
                    "min_years_experience": 3.0,
                }
            )
        if schema.__name__ == "ResumeAnalysis":
            return schema.model_validate(_resume_analysis_payload(prompt))
        if schema.__name__ == "OfferDraft":
            return schema.model_validate(
                {
                    "subject": "Job Offer - Senior Engineer",
                    "body": "Dear Bob Jones,\n\nWe are pleased to offer you the position of Senior Engineer at Tenant Alpha.\n\nSalary: 120000 USD\nStart Date: 2026-02-01\n\nSincerely,\nTenant Alpha",
                }
            )
        raise ValueError(f"No fake response defined for schema: {schema.__name__}")


class GeminiLLMClient(LLMClient):
    """Gemini client using google-genai with JSON response mode."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = GenAIClient(api_key=settings.GEMINI_API_KEY)
        self._model = settings.GEMINI_MODEL
        self.model_name = settings.GEMINI_MODEL

    def generate_json(
        self, system: str, prompt: str, schema: type[T]
    ) -> T:
        """Generate JSON response validated against schema with one retry."""
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
        )

        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                text = response.text or ""
                text = text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                return schema.model_validate_json(text)
            except (ValidationError, Exception):
                if attempt == 0:
                    continue
                raise LLMError("LLM generation failed after retry") from None

        raise LLMError("LLM generation failed after retry")


def get_llm_client() -> LLMClient:
    """Factory that returns the appropriate LLM client based on settings."""
    settings = get_settings()
    if settings.LLM_PROVIDER == "gemini":
        return GeminiLLMClient()
    return FakeLLMClient()