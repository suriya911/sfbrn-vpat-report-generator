from vpat_reviewer.domain.normalization import CANONICAL_STATUSES, normalize_status


def test_canonical_mappings():
    assert normalize_status("Supports") == "Supports"
    assert normalize_status("Partially Supports") == "Partially Supports"
    assert normalize_status("Does Not Support") == "Does Not Support"
    assert normalize_status("Not Applicable") == "Not Applicable"
    assert normalize_status("N/A") == "Not Applicable"
    assert normalize_status("") == "Not Evaluated"


def test_partial_never_collapses_to_supports():
    # Regression (v9 FIX F): "Partial Support" must NOT become "Supports".
    assert normalize_status("Partial Support") == "Partially Supports"
    assert normalize_status("partial support") == "Partially Supports"
    assert normalize_status("Supports with Exceptions") == "Partially Supports"
    assert normalize_status("limited support") == "Partially Supports"


def test_fuzzy_and_typos():
    assert normalize_status("does not meet") == "Does Not Support"
    assert normalize_status("unsupported") == "Does Not Support"
    assert normalize_status("fully supports") == "Supports"
    assert normalize_status("heading cell") == "Not Evaluated"


def test_output_is_always_canonical():
    for raw in ["", "weird value", "supports", "n/a", "partial", "not evaluated"]:
        assert normalize_status(raw) in CANONICAL_STATUSES
