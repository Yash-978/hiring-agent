"""Offer letter drafting agent."""

from pydantic import BaseModel

from app.agents.llm import LLMClient


class OfferDraft(BaseModel):
    """Structured output for offer letter draft."""
    subject: str
    body: str


SYSTEM_PROMPT = (
    "You are an expert HR professional drafting formal offer letters. "
    "Use ONLY the provided facts: candidate name, job title, salary, "
    "currency, start date, and company name. "
    "Never invent benefits, policies, bonuses, equity, relocation, "
    "probation periods, or any other terms not explicitly provided. "
    "Write in a formal, professional tone suitable for an employment offer letter."
)


def draft_offer(
    client: LLMClient,
    candidate_name: str,
    job_title: str,
    salary: float,
    currency: str,
    start_date: str,
    company_name: str,
) -> OfferDraft:
    """Draft an offer letter using the LLM client."""
    prompt = (
        f"Candidate: {candidate_name}\n"
        f"Job Title: {job_title}\n"
        f"Salary: {salary} {currency}\n"
        f"Start Date: {start_date}\n"
        f"Company: {company_name}\n\n"
        "Draft a formal offer letter with subject and body."
    )
    return client.generate_json(SYSTEM_PROMPT, prompt, OfferDraft)