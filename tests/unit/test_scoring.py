from vpat_reviewer.domain.models import VPATCriterion, VPATDocument
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.domain.policy import GradingPolicy, ScoreBand
from vpat_reviewer.domain.scoring import compliance_score, get_barriers


def crit(cid: str, level: str, status: str) -> VPATCriterion:
    return VPATCriterion(
        criterion_id=cid,
        level=level,
        raw_status=status,
        normalized_status=normalize_status(status),
    )


def sample() -> VPATDocument:
    d = VPATDocument()
    d.criteria = [
        crit("1.4.3", "AA", "Supports"),
        crit("1.4.4", "AA", "Supports"),
        crit("2.4.6", "AA", "Supports"),
        crit("3.3.3", "AA", "Partially Supports"),
        crit("1.2.4", "AA", "Not Applicable"),
        crit("4.1.3", "AA", "Not Evaluated"),
        crit("2.1.1", "A", "Supports"),
    ]
    return d


def test_na_excluded_from_denominator():
    info = compliance_score(sample())
    assert info["na_excluded"] == 1
    assert info["total"] == 5  # 6 AA - 1 NA
    assert info["supported"] == 3
    assert info["score"] == 60


def test_all_supported_is_100():
    d = VPATDocument()
    d.criteria = [crit(c, "AA", "Supports") for c in ("1.4.3", "1.4.4", "2.4.6")]
    assert compliance_score(d)["score"] == 100


def test_no_reviewable_returns_none():
    d = VPATDocument()
    d.criteria = [crit("1.2.4", "AA", "Not Applicable"), crit("2.1.1", "A", "Supports")]
    assert compliance_score(d)["score"] is None


def test_barriers_exclude_supports_and_na():
    ids = {b.criterion_id for b in get_barriers(sample())}
    assert ids == {"3.3.3", "4.1.3"}


def test_message_band_matches_score():
    assert "Limited accessibility support" in compliance_score(sample())["message"]


# ── editable policy ───────────────────────────────────────────────────────────


def test_policy_can_count_partial_as_supported():
    policy = GradingPolicy.default().with_changes(
        supported_statuses=("Supports", "Partially Supports")
    )
    # Now 4 of 5 reviewable count as supported -> 80.
    assert compliance_score(sample(), policy)["score"] == 80


def test_policy_can_grade_level_a():
    policy = GradingPolicy.default().with_changes(graded_level="A")
    info = compliance_score(sample(), policy)
    assert info["total"] == 1 and info["score"] == 100


def test_policy_can_change_score_band_message():
    policy = GradingPolicy.default().with_changes(
        score_bands=(ScoreBand(0, "Custom", "Custom band message."),)
    )
    assert compliance_score(sample(), policy)["message"] == "Custom band message."
