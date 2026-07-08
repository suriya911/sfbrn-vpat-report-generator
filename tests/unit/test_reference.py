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


def test_workarounds_and_title_helpers():
    assert isinstance(workarounds("1.1.1"), list)
    assert workarounds("9.9.9") == []
    assert title("2.4.7") == "Focus Visible"
