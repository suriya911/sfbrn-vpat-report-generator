"""Fuzzy-branch coverage for ``normalize_status``.

The teammate's ``test_normalization`` covers the map and the partial-vs-supports
ordering. These reach the *fallback* branches used when a vendor phrases a status
in prose the map doesn't contain — the substring checks, which are the last line
of defence before a status goes unread.
"""

from vpat_reviewer.domain.normalization import normalize_status


def test_prefix_of_a_map_key_still_resolves():
    # Not an exact key, but starts with one ("supported") -> the startswith path.
    assert normalize_status("supported across the entire product") == "Supports"


def test_prose_does_not_support():
    assert normalize_status("the product does not support this feature") == "Does Not Support"
    assert normalize_status("this behaviour is currently unsupported") == "Does Not Support"


def test_prose_not_applicable():
    assert normalize_status("this criterion is not applicable to the web app") == "Not Applicable"


def test_prose_not_evaluated():
    assert normalize_status("this was not evaluated during the audit") == "Not Evaluated"
