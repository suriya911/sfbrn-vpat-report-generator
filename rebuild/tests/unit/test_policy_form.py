from vpat_reviewer.config import policy_form
from vpat_reviewer.domain.policy import GradingPolicy


def test_set_compliance_threshold():
    p, err = policy_form.set_field(GradingPolicy.default(), "compliance_threshold", "85")
    assert err is None
    assert p.compliance_threshold == 85


def test_set_threshold_invalid_leaves_policy_unchanged():
    base = GradingPolicy.default()
    p, err = policy_form.set_field(base, "compliance_threshold", "abc")
    assert err is not None
    assert p == base


def test_set_threshold_out_of_range_rejected():
    _, err = policy_form.set_field(GradingPolicy.default(), "compliance_threshold", "150")
    assert err is not None  # validate() catches 0..100


def test_set_graded_level():
    p, err = policy_form.set_field(GradingPolicy.default(), "graded_level", "A")
    assert err is None
    assert p.graded_level == "A"


def test_set_supported_statuses_from_csv():
    p, err = policy_form.set_field(
        GradingPolicy.default(), "supported_statuses", "Supports, Partially Supports"
    )
    assert err is None
    assert p.supported_statuses == ("Supports", "Partially Supports")


def test_set_supported_statuses_rejects_unknown():
    _, err = policy_form.set_field(GradingPolicy.default(), "supported_statuses", "Bogus")
    assert err is not None
    assert "unknown" in err.lower()


def test_set_unknown_field():
    _, err = policy_form.set_field(GradingPolicy.default(), "nope", "x")
    assert err is not None
    assert "unknown field" in err


def test_set_band_min_and_label():
    p, err = policy_form.set_band(GradingPolicy.default(), 0, "min_score", "95")
    assert err is None
    assert p.score_bands[0].min_score == 95
    p2, err2 = policy_form.set_band(p, 0, "label", "Excellent")
    assert err2 is None
    assert p2.score_bands[0].label == "Excellent"


def test_set_band_out_of_range():
    _, err = policy_form.set_band(GradingPolicy.default(), 99, "label", "x")
    assert err is not None
    assert "out of range" in err


def test_set_band_removing_catchall_is_rejected():
    # The lowest band (index 3) is the catch-all at min_score 0; raising it breaks validity.
    _, err = policy_form.set_band(GradingPolicy.default(), 3, "min_score", "40")
    assert err is not None
    assert "catch-all" in err


def test_current_values_shape():
    v = policy_form.current_values(GradingPolicy.default())
    assert v["graded_level"] == "AA"
    assert v["compliance_threshold"] == 90
    assert len(v["score_bands"]) == 4
    assert v["supported_statuses"] == ["Supports"]
