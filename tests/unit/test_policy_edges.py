"""Coverage for GradingPolicy's validation and defensive from_dict paths."""

from vpat_reviewer.domain.policy import GradingPolicy


def test_band_for_below_every_band_falls_back_to_the_lowest():
    p = GradingPolicy.default()
    assert p.band_for(-1) == min(p.score_bands, key=lambda b: b.min_score)


def test_validate_flags_missing_graded_level():
    problems = GradingPolicy.default().with_changes(graded_level="").validate()
    assert any("graded_level" in m for m in problems)


def test_validate_flags_empty_supported_statuses():
    problems = GradingPolicy.default().with_changes(supported_statuses=()).validate()
    assert any("supported_statuses" in m for m in problems)


def test_validate_flags_empty_score_bands():
    problems = GradingPolicy.default().with_changes(score_bands=()).validate()
    assert any("score_bands" in m for m in problems)


def test_default_policy_is_valid():
    assert GradingPolicy.default().validate() == []


def test_from_dict_ignores_a_malformed_flag():
    # A flag entry that isn't a {kind, count} object falls back to the default
    # rather than crashing the whole policy load.
    p = GradingPolicy.from_dict({"access_flags": {"campus_wide": "not-a-flag-dict"}})
    assert p.access_flags["campus_wide"].count == 1
