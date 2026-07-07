from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.models import VPATCriterion
from vpat_reviewer.domain.policy import HIGH, Flag, GradingPolicy, ScoreFlag
from vpat_reviewer.domain.scoring import ScoreInfo


def barrier(status: str) -> VPATCriterion:
    return VPATCriterion(criterion_id="x", level="AA", normalized_status=status)


def score(value: int | None) -> ScoreInfo:
    return ScoreInfo(score=value, supported=0, total=0, total_aa_found=0, na_excluded=0, message="")


def test_scale_not_double_counted():
    # Regression (v9 FIX G): campus-wide on BOTH axes must not stack to High.
    answers = {
        "audience": "campus_wide",
        "access_impact": "no_limit",
        "legal_exposure": "low",
        "deployment": "campus_wide",
    }
    result = calculate_impact(answers, [], score(85))
    assert result["suggested_level"] in ("Low", "Medium")
    assert result["suggested_level"] != "High"


def test_denies_access_is_high():
    answers = {
        "audience": "campus_wide",
        "access_impact": "denies_access",
        "legal_exposure": "high",
        "deployment": "campus_wide",
    }
    assert calculate_impact(answers, [], score(40))["suggested_level"] == "High"


def test_core_blocked_pushes_high():
    answers = {
        "audience": "individual",
        "access_impact": "no_limit",
        "legal_exposure": "high",
        "deployment": "individual",
    }
    # core-blocked (+1 high) plus legal high (+1 high) => 2 high => High.
    result = calculate_impact(answers, [barrier("Does Not Support")], score(85))
    assert result["suggested_level"] == "High"


def test_low_when_nothing_flags():
    answers = {
        "audience": "individual",
        "access_impact": "no_limit",
        "legal_exposure": "low",
        "deployment": "individual",
    }
    assert calculate_impact(answers, [], score(95))["suggested_level"] == "Low"


# ── editable policy ───────────────────────────────────────────────────────────


def test_policy_can_make_score_threshold_stricter():
    answers = {
        "audience": "individual",
        "access_impact": "no_limit",
        "legal_exposure": "low",
        "deployment": "individual",
    }
    # Make any score below 101 add a single high flag => Medium per default rule.
    policy = GradingPolicy.default().with_changes(score_flags=(ScoreFlag(101, HIGH, 1),))
    assert calculate_impact(answers, [], score(90), policy)["suggested_level"] == "Medium"


def test_policy_flag_weights_reachable():
    # Sanity: the Flag structure the policy uses is what impact consumes.
    assert Flag(HIGH, 2).kind == HIGH
