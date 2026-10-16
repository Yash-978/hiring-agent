"""Deterministic scoring. The LLM judges each criterion; this code computes the score."""
import re
import unicodedata

VERDICT_POINTS = {"met": 1.0, "partial": 0.5, "not_met": 0.0, "unknown": 0.0}
WEIGHTS = {"must_have": 0.70, "nice_to_have": 0.20, "experience": 0.10}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_evidence(evidence: str, resume_text: str) -> bool:
    """True only if the quoted evidence really appears in the resume text."""
    if not evidence or _norm(evidence) in ("", "none"):
        return False
    return _norm(evidence) in _norm(resume_text)


def compute_score(criteria: list[dict]) -> dict:
    """criteria items need: kind, verdict, evidence_verified. Returns score 0-100 + breakdown."""
    breakdown: dict[str, dict] = {}
    total = 0.0
    used_weight = 0.0
    for kind, weight in WEIGHTS.items():
        items = [c for c in criteria if c["kind"] == kind]
        if not items:
            continue
        points = []
        for c in items:
            verdict = c["verdict"]
            # A positive claim without verified evidence counts as unknown.
            if verdict in ("met", "partial") and not c.get("evidence_verified"):
                verdict = "unknown"
            points.append(VERDICT_POINTS.get(verdict, 0.0))
        ratio = sum(points) / len(points)
        breakdown[kind] = {"ratio": round(ratio, 3), "weight": weight, "count": len(items)}
        total += ratio * weight
        used_weight += weight
    score = round(100 * total / used_weight, 1) if used_weight else 0.0
    return {"score": score, "breakdown": breakdown}