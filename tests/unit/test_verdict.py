"""Branch coverage for the deterministic verdict (``domain/verdict.py``).

``classify_report`` is the offline fallback that runs on every review where the
model is unavailable, so each of its rules is worth pinning. The existing
``test_verdict_samples`` drives it through whole sample documents; this walks the
rules directly, including the two "Deny" paths those samples don't reach.
"""

from vpat_reviewer.domain.verdict import CATEGORIES, classify_report


def test_absent_score_defers_to_a_human():
    # None is an *absent* score, not a low one — it must resolve to a person.
    assert classify_report(None, "Low", 0, "no_limit") == "Needs Manual Review"


def test_denies_access_at_high_impact_is_deny():
    assert classify_report(80, "High", 1, "denies_access") == "Deny"


def test_high_impact_and_low_score_is_deny():
    # High impact with a sub-50 score is a Deny even without denies_access.
    assert classify_report(40, "High", 3, "limits_some") == "Deny"


def test_high_impact_with_a_workable_score_needs_taap():
    assert classify_report(75, "High", 2, "limits_some") == "Need TAAP"


def test_clean_high_score_is_good_to_go():
    assert classify_report(95, "Low", 0, "no_limit") == "Good to Go"


def test_high_score_but_barriers_present_is_minor_issue():
    # At/above the cut but with barriers → not clean enough for Good to Go.
    assert classify_report(95, "Low", 2, "no_limit") == "Minor Issue"


def test_mid_score_is_minor_issue():
    assert classify_report(72, "Medium", 1, "limits_some") == "Minor Issue"


def test_low_score_needs_manual_review():
    assert classify_report(60, "Medium", 1, "limits_some") == "Needs Manual Review"


def test_custom_good_cut_is_respected():
    # A perfect score below a raised bar drops out of Good to Go.
    assert classify_report(90, "Low", 0, "no_limit", good_cut=95) == "Minor Issue"


def test_result_is_always_one_of_the_five_categories():
    for score in (None, 0, 49, 50, 69, 70, 89, 90, 100):
        for impact in ("Low", "Medium", "High"):
            for access in ("no_limit", "limits_some", "denies_access"):
                assert classify_report(score, impact, 0, access) in CATEGORIES
