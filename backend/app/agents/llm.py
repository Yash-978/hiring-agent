"""LLM client protocol and implementations."""

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


class FakeLLMClient(LLMClient):
    """Deterministic fake client for testing."""

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
            return schema.model_validate(
                {
                    "candidate": {
                        "full_name": "Alice Smith",
                        "email": "alice@example.com",
                        "phone": None,
                        "location": None,
                        "current_title": "Backend Engineer",
                        "total_years_experience": 5.0,
                        "education": ["BSc Computer Science"],
                        "skills": ["Python", "FastAPI", "Docker"],
                    },
                    "criteria": [
                        {
                            "criterion": "Python",
                            "kind": "must_have",
                            "verdict": "met",
                            "evidence": "Python and FastAPI",
                            "note": "Uses Python daily.",
                        },
                        {
                            "criterion": "FastAPI",
                            "kind": "must_have",
                            "verdict": "met",
                            "evidence": "Python and FastAPI",
                            "note": "Built FastAPI services.",
                        },
                        {
                            "criterion": "Docker",
                            "kind": "nice_to_have",
                            "verdict": "partial",
                            "evidence": "Docker",
                            "note": "Some Docker exposure.",
                        },
                        {
                            "criterion": "5 years of experience",
                            "kind": "experience",
                            "verdict": "met",
                            "evidence": "5 years Python",
                            "note": "Meets the minimum.",
                        },
                    ],
                    "strengths": ["Strong Python skills"],
                    "concerns": ["Limited Kubernetes experience"],
                    "questions_for_candidate": ["Describe your largest FastAPI project."],
                    "recommendation": "shortlist",
                    "confidence": "medium",
                }
            )
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