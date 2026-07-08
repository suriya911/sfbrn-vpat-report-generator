from vpat_reviewer.config import policy_form
from vpat_reviewer.domain.policy import GradingPolicy


def _valid_values():
    return {
        "graded_level": "AA",
        "compliance_threshold": "85",
        "supported_statuses": ["Supports", "Partially Supports"],
        "excluded_statuses": ["Not Applicable"],
        "bands": [
            {"min_score": "90", "label": "Strong", "message": "m1"},
            {"min_score": "0", "label": "Risk", "message": "m2"},
        ],
    }


def test_from_form_success():
    p, errs = policy_form.from_form(GradingPolicy.default(), _valid_values())
    assert errs == []
    assert p is not None
    assert p.compliance_threshold == 85
    assert p.supported_statuses == ("Supports", "Partially Supports")
    assert p.score_bands[0].min_score == 90
    assert p.graded_level == "AA"


def test_from_form_bad_threshold():
    values = _valid_values()
    values["compliance_threshold"] = "not-a-number"
    p, errs = policy_form.from_form(GradingPolicy.default(), values)
    assert p is None
    assert any("threshold" in e.lower() for e in errs)


def test_from_form_missing_catchall_band():
    values = _valid_values()
    values["bands"] = [{"min_score": "50", "label": "X", "message": "y"}]
    p, errs = policy_form.from_form(GradingPolicy.default(), values)
    assert p is None
    assert any("catch-all" in e for e in errs)


def test_from_form_unknown_status():
    values = _valid_values()
    values["supported_statuses"] = ["Bogus"]
    p, errs = policy_form.from_form(GradingPolicy.default(), values)
    assert p is None
    assert any("Unknown supported status" in e for e in errs)


def test_from_form_roundtrips_through_dict():
    p, _ = policy_form.from_form(GradingPolicy.default(), _valid_values())
    assert p is not None
    assert GradingPolicy.from_dict(p.to_dict()) == p
