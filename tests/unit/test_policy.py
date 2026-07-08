from vpat_reviewer.domain.policy import GradingPolicy, ScoreBand


def test_default_is_valid():
    assert GradingPolicy.default().validate() == []


def test_status_classification():
    p = GradingPolicy.default()
    assert p.is_supported("Supports")
    assert p.is_excluded("Not Applicable")
    assert p.is_barrier("Partially Supports")
    assert p.is_barrier("Not Evaluated")
    assert not p.is_barrier("Supports")
    assert not p.is_barrier("Not Applicable")


def test_band_for():
    p = GradingPolicy.default()
    assert p.band_for(95).label == "Strong"
    assert p.band_for(80).label == "Moderate"
    assert p.band_for(60).label == "Limited"
    assert p.band_for(10).label == "High risk"


def test_roundtrip_to_from_dict():
    p = GradingPolicy.default()
    assert GradingPolicy.from_dict(p.to_dict()) == p


def test_roundtrip_after_edits():
    p = GradingPolicy.default().with_changes(
        compliance_threshold=80,
        graded_level="A",
        supported_statuses=("Supports", "Partially Supports"),
        score_bands=(ScoreBand(50, "Pass", "ok"), ScoreBand(0, "Fail", "no")),
    )
    assert GradingPolicy.from_dict(p.to_dict()) == p


def test_partial_dict_inherits_defaults():
    p = GradingPolicy.from_dict({"compliance_threshold": 70})
    assert p.compliance_threshold == 70
    assert p.graded_level == "AA"  # inherited
    assert p.supported_statuses == ("Supports",)  # inherited


def test_empty_dict_is_default():
    assert GradingPolicy.from_dict(None) == GradingPolicy.default()
    assert GradingPolicy.from_dict({}) == GradingPolicy.default()


def test_validate_flags_missing_catchall_band():
    bad = GradingPolicy.default().with_changes(score_bands=(ScoreBand(50, "x", "y"),))
    assert bad.validate()  # non-empty: no band with min_score <= 0


def test_validate_flags_bad_threshold():
    assert GradingPolicy.default().with_changes(compliance_threshold=150).validate()
