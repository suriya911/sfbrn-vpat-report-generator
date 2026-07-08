from vpat_reviewer.parsing.standards import detect_standards


def test_detects_wcag_aa_and_508():
    result = detect_standards("Conforms to WCAG 2.1 Level AA and Section 508.")
    assert result == ["WCAG 2.1 Level AA", "Section 508 (Revised 2017)"]


def test_level_aa_does_not_also_match_level_a():
    # "Level AA" must not also register "Level A" (negative lookahead).
    assert detect_standards("WCAG 2.1 Level AA") == ["WCAG 2.1 Level AA"]


def test_spelled_out_name():
    result = detect_standards("Web Content Accessibility Guidelines 2.0 Level A")
    assert "WCAG 2.0 Level A" in result


def test_en_301_549():
    assert "EN 301 549" in detect_standards("Also EN 301 549 applies.")


def test_none_found():
    assert detect_standards("no standards mentioned here") == []
