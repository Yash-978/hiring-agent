"""Deterministic scoring. The LLM judges each criterion; this code computes the score."""
import re
import unicodedata

VERDICT_POINTS = {"met": 1.0, "partial": 0.5, "not_met": 0.0, "unknown": 0.0}
WEIGHTS = {"must_have": 0.70, "nice_to_have": 0.20, "experience": 0.10}

# A missed must-have is a hard gap: one caps the score at 79, two or more at 59.
ONE_MUST_HAVE_MISS_CAP = 79.0
MULTIPLE_MUST_HAVE_MISS_CAP = 59.0


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def experience_ratio(years: float | None, min_years: float | None) -> float | None:
    """Candidate years over the job minimum, clamped to 0..1.

    Returns None when the job states no minimum, so the LLM's experience
    judgement stands. Unknown candidate years score 0.0: we never give credit
    for experience the resume does not state.
    """
    if min_years is None or min_years <= 0:
        return None
    if years is None:
        return 0.0
    return max(0.0, min(1.0, years / min_years))


def _effective_verdict(criterion: dict) -> str:
    """A positive verdict without verified evidence counts as unknown."""
    verdict = criterion["verdict"]
    if verdict in ("met", "partial") and not criterion.get("evidence_verified"):
        return "unknown"
    return verdict


def verify_evidence(evidence: str, resume_text: str) -> bool:
    """True only if the quoted evidence really appears in the resume text."""
    if not evidence or _norm(evidence) in ("", "none"):
        return False
    return _norm(evidence) in _norm(resume_text)


def compute_score(
    criteria: list[dict],
    experience_override: float | None = None,
) -> dict:
    """criteria items need: kind, verdict, evidence_verified. Returns score 0-100 + breakdown.

    When experience_override is given, the experience ratio is computed in code
    instead of from the LLM's experience criteria, and the experience weight
    always counts so a missing experience judgement cannot inflate the score.
    A hard gap on a must-have criterion caps the final score.
    """
    breakdown: dict[str, dict] = {}
    total = 0.0
    used_weight = 0.0
    for kind, weight in WEIGHTS.items():
        items = [c for c in criteria if c["kind"] == kind]
        if kind == "experience" and experience_override is not None:
            ratio = max(0.0, min(1.0, experience_override))
            breakdown[kind] = {
                "ratio": round(ratio, 3),
                "weight": weight,
                "count": max(len(items), 1),
            }
            total += ratio * weight
            used_weight += weight
            continue
        if not items:
            continue
        points = [VERDICT_POINTS.get(_effective_verdict(c), 0.0) for c in items]
        ratio = sum(points) / len(points)
        breakdown[kind] = {"ratio": round(ratio, 3), "weight": weight, "count": len(items)}
        total += ratio * weight
        used_weight += weight
    score = round(100 * total / used_weight, 1) if used_weight else 0.0

    # Hard gaps on must-have criteria cap the score, so a missed requirement
    # cannot be hidden by strong scores elsewhere.
    missed = sum(
        1
        for c in criteria
        if c["kind"] == "must_have" and _effective_verdict(c) == "not_met"
    )
    if missed >= 2:
        score = min(score, MULTIPLE_MUST_HAVE_MISS_CAP)
    elif missed == 1:
        score = min(score, ONE_MUST_HAVE_MISS_CAP)
    return {"score": score, "breakdown": breakdown}