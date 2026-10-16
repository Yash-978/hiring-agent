"""Tests for the deterministic scoring helpers in app.agents.scoring.

The LLM judges each criterion; scoring.py turns those judgments into a number.
These tests pin down the three rules that matter:
  1. evidence must actually appear in the resume (verify_evidence),
  2. a positive verdict without verified evidence counts as unknown,
  3. kinds with no criteria are dropped and the remaining weights re-normalized.
"""

from app.agents.scoring import (
    MULTIPLE_MUST_HAVE_MISS_CAP,
    ONE_MUST_HAVE_MISS_CAP,
    VERDICT_POINTS,
    WEIGHTS,
    compute_score,
    experience_ratio,
    verify_evidence,
)


def _crit(kind: str, verdict: str, verified: bool = True) -> dict:
    return {"kind": kind, "verdict": verdict, "evidence_verified": verified}


# ---------------------------------------------------------------------------
# verify_evidence
# ---------------------------------------------------------------------------


def test_verify_evidence_finds_quote_inside_resume() -> None:
    resume = "I built APIs with FastAPI every day."
    assert verify_evidence("built APIs with FastAPI", resume) is True


def test_verify_evidence_is_case_and_whitespace_insensitive() -> None:
    resume = "Python,   FastAPI and\nPostgreSQL"
    assert verify_evidence("python, fastapi", resume) is True


def test_verify_evidence_rejects_quote_not_present() -> None:
    assert verify_evidence("Expert in Kubernetes", "Python and FastAPI only") is False


def test_verify_evidence_rejects_empty_whitespace_and_none() -> None:
    for evidence in ("", "   ", "none", "NONE", "None"):
        assert verify_evidence(evidence, "anything at all") is False


def test_verify_evidence_handles_empty_resume() -> None:
    assert verify_evidence("Python", "") is False


def test_verify_evidence_ignores_unicode_compatibility_forms() -> None:
    # NFKC normalization folds full-width characters back to ASCII.
    assert verify_evidence("FastAPI", "ＦａｓｔＡＰＩ developer") is True


# ---------------------------------------------------------------------------
# compute_score: unverified positive verdicts become unknown
# ---------------------------------------------------------------------------


def test_unverified_met_counts_as_unknown() -> None:
    result = compute_score([_crit("must_have", "met", verified=False)])
    assert result["score"] == 0.0
    assert result["breakdown"]["must_have"]["ratio"] == 0.0


def test_unverified_partial_counts_as_unknown() -> None:
    result = compute_score([_crit("nice_to_have", "partial", verified=False)])
    assert result["score"] == 0.0


def test_missing_evidence_flag_is_treated_as_unverified() -> None:
    result = compute_score([{"kind": "must_have", "verdict": "met"}])
    assert result["score"] == 0.0


def test_verified_met_counts_full_points() -> None:
    result = compute_score([_crit("must_have", "met", verified=True)])
    assert result["score"] == 100.0


def test_negative_verdict_does_not_need_evidence() -> None:
    # not_met / unknown already score 0 even when marked verified.
    assert compute_score([_crit("must_have", "not_met", verified=False)])["score"] == 0.0
    assert compute_score([_crit("must_have", "unknown", verified=False)])["score"] == 0.0


# ---------------------------------------------------------------------------
# compute_score: missing kinds are re-normalized
# ---------------------------------------------------------------------------


def test_only_nice_to_have_is_renormalized_not_scaled_to_its_weight() -> None:
    result = compute_score(
        [
            _crit("nice_to_have", "met", True),
            _crit("nice_to_have", "not_met", True),
        ]
    )
    assert result["score"] == 50.0
    assert set(result["breakdown"]) == {"nice_to_have"}


def test_only_experience_is_renormalized() -> None:
    result = compute_score([_crit("experience", "partial", True)])
    assert result["score"] == 50.0


def test_absent_kinds_are_omitted_from_breakdown() -> None:
    result = compute_score([_crit("must_have", "met", True)])
    assert set(result["breakdown"]) == {"must_have"}


# ---------------------------------------------------------------------------
# compute_score: weighting across kinds and rounding
# ---------------------------------------------------------------------------


def test_weights_are_applied_across_kinds() -> None:
    criteria = [
        _crit("must_have", "met", True),
        _crit("nice_to_have", "not_met", True),
        _crit("experience", "met", True),
    ]
    result = compute_score(criteria)
    # total = 0.70*1 + 0.20*0 + 0.10*1 = 0.80 ; used = 1.0 -> 80.0
    assert result["score"] == 80.0
    assert result["breakdown"]["must_have"]["count"] == 1
    assert result["breakdown"]["nice_to_have"]["ratio"] == 0.0
    assert result["breakdown"]["experience"]["weight"] == WEIGHTS["experience"]


def test_breakdown_reports_ratio_weight_and_count() -> None:
    result = compute_score(
        [
            _crit("must_have", "met", True),
            _crit("must_have", "met", False),  # unverified -> unknown -> 0
        ]
    )
    breakdown = result["breakdown"]["must_have"]
    assert breakdown == {"ratio": 0.5, "weight": WEIGHTS["must_have"], "count": 2}
    assert result["score"] == 50.0


def test_score_is_rounded_to_one_decimal() -> None:
    result = compute_score(
        [
            _crit("must_have", "met", True),
            _crit("must_have", "met", True),
            _crit("must_have", "not_met", True),
        ]
    )
    # ratio = 2/3 ; used weight re-normalized to 0.70 -> 100 * 2/3 -> 66.7
    assert result["score"] == 66.7


def test_empty_criteria_scores_zero() -> None:
    result = compute_score([])
    assert result["score"] == 0.0
    assert result["breakdown"] == {}


def test_verdict_points_match_documented_values() -> None:
    assert VERDICT_POINTS == {"met": 1.0, "partial": 0.5, "not_met": 0.0, "unknown": 0.0}
    assert WEIGHTS == {"must_have": 0.70, "nice_to_have": 0.20, "experience": 0.10}


# ---------------------------------------------------------------------------
# experience_ratio: experience is computed in code, not by the LLM
# ---------------------------------------------------------------------------


def test_experience_ratio_clamps_to_one_when_over_minimum() -> None:
    assert experience_ratio(5.0, 3.0) == 1.0


def test_experience_ratio_is_proportional_below_minimum() -> None:
    assert experience_ratio(1.5, 3.0) == 0.5


def test_experience_ratio_without_minimum_is_none() -> None:
    assert experience_ratio(5.0, None) is None
    assert experience_ratio(5.0, 0.0) is None


def test_experience_ratio_with_unknown_years_is_zero() -> None:
    # No stated years never earns credit.
    assert experience_ratio(None, 3.0) == 0.0


# ---------------------------------------------------------------------------
# compute_score: the experience override always counts
# ---------------------------------------------------------------------------


def test_experience_override_replaces_llm_experience_verdict() -> None:
    criteria = [
        _crit("must_have", "met", True),
        _crit("experience", "met", True),  # the LLM's generous judgement
    ]
    # Code says the candidate has no experience, so the override wins.
    result = compute_score(criteria, experience_override=0.0)
    assert result["breakdown"]["experience"]["ratio"] == 0.0
    # Weights are re-normalized over the kinds that count: used = 0.80,
    # total = 0.70*1 + 0.10*0 = 0.70 -> 0.70/0.80 = 87.5
    assert result["score"] == 87.5


def test_experience_override_counts_even_without_experience_criteria() -> None:
    criteria = [_crit("must_have", "met", True)]
    result = compute_score(criteria, experience_override=1.0)
    assert set(result["breakdown"]) == {"must_have", "experience"}
    assert result["breakdown"]["experience"]["count"] == 1
    # total = 0.70*1 + 0.10*1 = 0.80 ; used = 0.80 -> 100.0
    assert result["score"] == 100.0


def test_omitting_the_override_keeps_the_old_behaviour() -> None:
    criteria = [_crit("must_have", "met", True)]
    result = compute_score(criteria)
    assert set(result["breakdown"]) == {"must_have"}
    assert result["score"] == 100.0


# ---------------------------------------------------------------------------
# compute_score: hard gaps on must-haves cap the score
# ---------------------------------------------------------------------------


def test_one_missed_must_have_caps_the_score() -> None:
    criteria = [
        _crit("must_have", "met", True),
        _crit("must_have", "met", True),
        _crit("must_have", "met", True),
        _crit("must_have", "met", True),
        _crit("must_have", "not_met", True),
        _crit("nice_to_have", "met", True),
        _crit("experience", "met", True),
    ]
    # ratio = 4/5 ; total = 0.8*0.70 + 0.20 + 0.10 = 0.86 -> 86.0, capped to 79.
    result = compute_score(criteria)
    assert result["score"] == ONE_MUST_HAVE_MISS_CAP == 79.0


def test_two_missed_must_haves_cap_the_score_harder() -> None:
    criteria = [
        _crit("must_have", "met", True),
        _crit("must_have", "met", True),
        _crit("must_have", "met", True),
        _crit("must_have", "met", True),
        _crit("must_have", "met", True),
        _crit("must_have", "not_met", True),
        _crit("must_have", "not_met", True),
        _crit("nice_to_have", "met", True),
        _crit("experience", "met", True),
    ]
    # 5/7*0.70 + 0.20 + 0.10 = 0.80 -> 80.0, capped to 59.
    assert compute_score(criteria)["score"] == MULTIPLE_MUST_HAVE_MISS_CAP == 59.0


def test_a_single_miss_below_the_cap_is_untouched() -> None:
    criteria = [
        _crit("must_have", "met", True),
        _crit("must_have", "not_met", True),
        _crit("nice_to_have", "met", True),
        _crit("experience", "met", True),
    ]
    # 0.5*0.70 + 0.20 + 0.10 = 0.65 -> 65.0, already below the 79 cap.
    assert compute_score(criteria)["score"] == 65.0


def test_unverified_positive_must_have_is_unknown_not_a_miss() -> None:
    # A positive verdict without evidence becomes unknown, which is not a hard
    # gap, so it never triggers the cap.
    criteria = [
        _crit("must_have", "met", True),
        _crit("must_have", "met", False),  # -> unknown
        _crit("must_have", "met", False),  # -> unknown
        _crit("nice_to_have", "met", True),
        _crit("experience", "met", True),
    ]
    result = compute_score(criteria)
    # 1/3*0.70 + 0.20 + 0.10 = 0.5333 -> 53.3 ; no not_met, so no cap.
    assert result["score"] == 53.3
