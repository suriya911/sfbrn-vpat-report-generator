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


def test_does_not_apply_is_out_of_scope_not_a_failure():
    """A real ACR answers 4.1.1 Parsing (which WCAG 2.2 removed) "Does Not Apply".

    It opens with "does not", but it means the criterion is out of scope rather
    than failed -- the difference between an excluded row and a barrier.
    """
    assert normalize_status("Does Not Apply") == "Not Applicable"
    assert normalize_status("does not apply") == "Not Applicable"


def test_target_prefixed_status():
    """Multi-target ACRs answer per surface: "Web: Supports"."""
    assert normalize_status("Web: Supports") == "Supports"
    assert normalize_status("Web: Partially Supports") == "Partially Supports"


def test_output_is_always_canonical():
    for raw in ["", "weird value", "supports", "n/a", "partial", "not evaluated"]:
        assert normalize_status(raw) in CANONICAL_STATUSES
