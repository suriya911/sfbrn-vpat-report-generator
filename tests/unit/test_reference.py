from vpat_reviewer.parsing.criteria import WCAG_LEVELS
from vpat_reviewer.reference import (
    REQUIRED_IDS,
    all_criteria,
    has_all_required,
    lookup,
    title,
    workarounds,
)


def test_dataset_loads():
    data = all_criteria()
    assert len(data) >= 54
    assert "1.4.3" in data


def test_lookup_known_criterion():
    e = lookup("1.4.3")
    assert e is not None
    assert e["title"] == "Contrast (Minimum)"
    assert e["level"] == "AA"
    assert e["principle"] == "Perceivable"
    assert e["description"]
    assert e["plain"]


def test_lookup_unknown():
    assert lookup("9.9.9") is None
    assert lookup("") is None


def test_has_all_required():
    ok, missing = has_all_required()
    assert ok, f"missing required criteria: {missing}"


def test_every_required_id_present_with_description():
    data = all_criteria()
    for cid in REQUIRED_IDS:
        assert cid in data, f"{cid} missing from dataset"
        assert data[cid]["description"], f"{cid} has no description"


def test_every_graded_criterion_has_reference_text():
    """The parser must not grade a criterion the report cannot explain.

    ``WCAG_LEVELS`` decides what counts toward the score; ``wcag.json`` supplies
    the text the report quotes. When the two drift apart, criteria are scored
    with nothing to say about them -- which is how 3.2.6 and 3.3.7 sat in the AA
    denominator for months with no reference entry.
    """
    data = all_criteria()
    graded = {cid for cid, level in WCAG_LEVELS.items() if level in ("A", "AA")}
    missing = sorted(graded - set(data))
    assert not missing, f"graded but absent from wcag.json: {missing}"


def test_levels_agree_between_parser_and_reference():
    """One criterion, one level. Disagreement moves rows in and out of the score."""
    mismatched = {
        cid: (level, all_criteria()[cid]["level"])
        for cid, level in WCAG_LEVELS.items()
        if cid in all_criteria() and all_criteria()[cid]["level"] != level
    }
    assert not mismatched, f"WCAG_LEVELS vs wcag.json disagree: {mismatched}"


def test_wcag_22_level_a_additions():
    """Consistent Help and Redundant Entry are Level A. Both were graded as AA."""
    assert WCAG_LEVELS["3.2.6"] == "A"
    assert WCAG_LEVELS["3.3.7"] == "A"


def test_workarounds_and_title_helpers():
    assert isinstance(workarounds("1.1.1"), list)
    assert workarounds("9.9.9") == []
    assert title("2.4.7") == "Focus Visible"
