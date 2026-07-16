"""Coverage for the text-cleanup helpers (``parsing/text_cleanup.py``)."""

from vpat_reviewer.parsing.text_cleanup import clean_extracted_text, is_blank_or_garbage


def test_blank_values_are_garbage():
    assert is_blank_or_garbage("") is True
    assert is_blank_or_garbage("   ") is True


def test_boilerplate_prefixes_are_garbage():
    assert is_blank_or_garbage("Notes: internal only") is True
    assert is_blank_or_garbage("Contact information: a@b.com") is True
    assert is_blank_or_garbage("N/A") is True


def test_too_short_to_mean_anything_is_garbage():
    assert is_blank_or_garbage("ok") is True  # len < 3


def test_real_remark_is_kept():
    assert is_blank_or_garbage("Supports keyboard navigation throughout") is False


def test_clean_strips_page_numbers_and_rules():
    out = clean_extracted_text("Real body text\nPage 3 of 10\n____________")
    assert "Page 3 of 10" not in out
    assert "____________" not in out
    assert "Real body text" in out
