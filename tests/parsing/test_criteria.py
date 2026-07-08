from vpat_reviewer.parsing.criteria import (
    clean_criterion_title,
    clean_remarks,
    parse_from_tables,
    parse_from_text,
)


def test_three_column_table():
    tables = [
        [
            ["Criteria", "Conformance Level", "Remarks"],
            ["1.4.3 Contrast (Minimum) (Level AA)", "Partially Supports", "Some low contrast."],
            ["2.1.1 Keyboard (Level A)", "Supports", ""],
        ]
    ]
    crits = parse_from_tables(tables)
    assert [c.criterion_id for c in crits] == ["1.4.3", "2.1.1"]
    assert crits[0].level == "AA"
    assert crits[0].normalized_status == "Partially Supports"
    assert crits[0].remarks == "Some low contrast."
    assert crits[1].normalized_status == "Supports"


def test_nine_column_table_reads_cols_3_and_6():
    row = [
        "1.4.3 Contrast (Minimum) (Level AA)",
        "",
        "",
        "Does Not Support",
        "",
        "",
        "Bad contrast throughout.",
        "",
        "",
    ]
    crits = parse_from_tables([[row, row]])  # >=2 rows so the table is considered
    assert len(crits) == 1
    assert crits[0].normalized_status == "Does Not Support"
    assert crits[0].remarks == "Bad contrast throughout."


def test_duplicate_criterion_ids_deduped():
    tables = [
        [
            ["1.4.3 Contrast (Minimum) (Level AA)", "Supports", ""],
            ["1.4.3 Contrast (Minimum) (Level AA)", "Does Not Support", "dup"],
        ]
    ]
    crits = parse_from_tables(tables)
    assert len(crits) == 1
    assert crits[0].normalized_status == "Supports"  # first wins


def test_text_fallback_status_and_remarks():
    text = (
        "1.4.4 Resize Text (Level AA)\n"
        "Partially Supports\n"
        "Remarks:\n"
        "Text resizes to 150%.\n"
        "2.4.7 Focus Visible (Level AA)\n"
        "Supports\n"
    )
    crits = parse_from_text(text, set())
    assert [c.criterion_id for c in crits] == ["1.4.4", "2.4.7"]
    assert crits[0].normalized_status == "Partially Supports"
    assert "Text resizes to 150%." in crits[0].remarks
    assert crits[1].normalized_status == "Supports"


def test_text_fallback_respects_seen_ids():
    crits = parse_from_text("1.4.3 Contrast (Minimum) (Level AA)\nSupports\n", {"1.4.3"})
    assert crits == []


def test_clean_criterion_title_strips_crossrefs():
    assert (
        clean_criterion_title("Contrast (Minimum) Also applies to: 1.4.6") == "Contrast (Minimum)"
    )


def test_clean_remarks_strips_prefix_and_watermark():
    assert clean_remarks("Remarks: Works well.") == "Works well."
