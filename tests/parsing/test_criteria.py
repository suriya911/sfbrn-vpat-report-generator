from vpat_reviewer.parsing.criteria import (
    clean_criterion_title,
    clean_remarks,
    heal_kerning_splits,
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


# --- Real-corpus table shapes -------------------------------------------------
#
# The rows below are transcribed from the PDFs in docs/completed_forms. Vendors
# do not agree on table width, and the status column is wherever their template
# put it -- so the parser must find the status by *looking*, not by trusting an
# index. Each of these reproduces a bug that silently degraded whole documents
# to "Not Evaluated".


def test_h5p_five_column_table():
    """H5P.com: width 5, status in col[2]. Was read as 3col -> empty col[1]."""
    row = [
        "1.1.1 Non-text Content (Level A)",
        "",
        "Supports",
        "",
        "Example: All images that aren't strictly background images have an "
        "input field where authors may provide alternative texts.",
    ]
    crits = parse_from_tables([[row, row]])
    assert len(crits) == 1
    assert crits[0].normalized_status == "Supports"
    assert crits[0].remarks.startswith("Example: All images")


def test_atrium_eight_column_table_with_target_prefix():
    """Atrium: width 8, status in col[3], prefixed 'Web:'.

    ``len(row) >= 9`` is false at width 8, so this fell to the 3col branch and
    read an empty col[1] -- 55 of 56 criteria became "Not Evaluated".
    """
    row = [
        "1.1.1 Non-text Content (Level A)\nAlso applies to:\nRevised Section 508\n"
        "• 501 (Web)(Software)\n• 504.2 (Authoring Tool)",
        "",
        "",
        "Web: Partially Supports",
        "",
        "",
        "Web: Non-text content presented to the user in the product has a text "
        "alternative in most cases.",
        "",
    ]
    crits = parse_from_tables([[row, row]])
    assert len(crits) == 1
    assert crits[0].criterion_id == "1.1.1"
    assert crits[0].normalized_status == "Partially Supports"
    # The target prefix belongs to the column header, not the vendor's answer.
    assert crits[0].raw_status == "Partially Supports"
    assert "Non-text content presented" in crits[0].remarks
    # "Also applies to:" cross-references must not leak into the title.
    assert crits[0].title == "Non-text Content"


def test_canvas_multiline_cell_with_wrapped_level():
    """Canvas: the criterion name, its W3C URL, and "(Level A)" are on separate
    lines *within one cell*. CRIT_RE without DOTALL matched nothing at all, so
    every Canvas row fell through to the text parser.
    """
    row = [
        "1.1.1 Non-text Content\n(http://www.w3.org/TR/WCAG20/#text-equiv-all)\n(Level A)",
        "Supports",
        "Canvas provides text alternatives to default non-text content.",
    ]
    crits = parse_from_tables([[row, row]])
    assert len(crits) == 1
    assert crits[0].criterion_id == "1.1.1"
    assert crits[0].level == "A"
    assert crits[0].normalized_status == "Supports"
    # The URL is noise for a human reader and for the LLM stage.
    assert "http" not in crits[0].title
    assert crits[0].title == "Non-text Content"


def test_canvas_status_wrapped_across_lines():
    """Canvas wraps "Not Applicable" as "Not\\nApplicable" inside its cell."""
    row = [
        "1.2.4 Captions (Live)\n(http://www.w3.org/TR/WCAG20/#media-equiv-real-time-captions)\n"
        "(Level AA)",
        "Not\nApplicable",
        "Canvas does not contain live audio or video functionality.",
    ]
    crits = parse_from_tables([[row, row]])
    assert len(crits) == 1
    assert crits[0].normalized_status == "Not Applicable"


def test_icims_watermark_polluted_status_cell():
    """iCIMS: a Box preview watermark bleeds into the status cell.

    The overlay is stamped across the page, so its characters land inside the
    cell's bbox and interleave with the real text -- note the '2' *inside*
    "Applicable". Conformance values are alphabetic, so non-alphabetic noise can
    be dropped. The digit must be deleted rather than replaced with a space, or
    "Not Applicab2le" becomes "Not Applicab le".
    """
    rows = [
        ["1.1.1 Non-text Content (Level A)", "4\nSupports 2\n3-\n0", "Text alternatives exist."],
        ["1.2.1 Audio-only (Prerecorded) (Level A)", "5-\nNot Applicab2le", "Not present."],
        ["1.2.2 Captions (Prerecorded) (Level A)", "0\nNot Applic2able\n,", "Not present."],
    ]
    crits = parse_from_tables([rows])
    assert [c.normalized_status for c in crits] == [
        "Supports",
        "Not Applicable",
        "Not Applicable",
    ]
    # The recovered status should read cleanly for the downstream LLM stage.
    assert crits[1].raw_status == "Not Applicable"


def test_denoising_does_not_invent_a_status():
    """Stripping noise must not turn prose into a conformance value."""
    rows = [
        ["1.1.1 Non-text Content (Level A)", "Supports 2 of 3 cases", "x"],
        ["1.2.1 Audio-only (Prerecorded) (Level A)", "See section 4.2 below", "y"],
    ]
    crits = parse_from_tables([rows])
    assert [c.raw_status for c in crits] == ["", ""]


def test_status_column_found_regardless_of_width():
    """The invariant behind all of the above: find the status by looking."""
    for width, status_col in ((3, 1), (5, 2), (8, 3), (9, 3)):
        row = [""] * width
        row[0] = "1.4.3 Contrast (Minimum) (Level AA)"
        row[status_col] = "Does Not Support"
        crits = parse_from_tables([[row, row]])
        assert len(crits) == 1, f"width {width}"
        assert crits[0].normalized_status == "Does Not Support", f"width {width}"


def test_atrium_remarks_split_across_continuation_rows():
    """Atrium emits one table row per *line* of a long remarks cell.

    Only the first row names the criterion; the rest carry nothing but the next
    line of prose in the remarks column. Reading row-by-row keeps the opening
    line and throws away the substance.
    """
    table = [
        [None, "Criteria", None, "Conformance Level", None, None, "Remarks and Explanations", None],
        [
            "1.1.1 Non-text Content (Level A)\nAlso applies to:\nRevised Section 508",
            "",
            "",
            "Web: Partially Supports",
            "",
            "",
            "Web: Non-text content presented to the user in the",
            "",
        ],
        ["", "", "", "", "", "", "product has text alternatives that serve the equivalent", ""],
        ["", "", "", "", "", "", "purpose. Exceptions include:", ""],
        ["", "", "", "", "", "", 'The "Atrium University" logo image has', ""],
        ["", "", "", "", "", "", "incomplete alternative text on the Footer", ""],
    ]
    crits = parse_from_tables([table])
    assert len(crits) == 1
    assert crits[0].normalized_status == "Partially Supports"
    remarks = crits[0].remarks
    assert remarks.startswith("Non-text content presented to the user in the product has")
    assert "Exceptions include:" in remarks
    assert "incomplete alternative text on the Footer" in remarks


def test_continuation_rows_stop_at_the_next_criterion():
    """A row with its own criterion or status is never folded into the one above."""
    table = [
        ["1.1.1 Non-text Content (Level A)", "Supports", "First remark"],
        ["", "", "continued"],
        ["1.4.3 Contrast (Minimum) (Level AA)", "Does Not Support", "Second remark"],
        ["", "", "also continued"],
    ]
    crits = parse_from_tables([table])
    assert [c.criterion_id for c in crits] == ["1.1.1", "1.4.3"]
    assert crits[0].remarks == "First remark continued"
    assert crits[1].remarks == "Second remark also continued"


def test_repeated_header_row_is_not_absorbed_as_remarks():
    """The ITI headers reprint on every page of a long table."""
    table = [
        ["1.1.1 Non-text Content (Level A)", "Supports", "A remark"],
        ["Criteria", "Conformance Level", "Remarks and Explanations"],
        ["1.4.3 Contrast (Minimum) (Level AA)", "Supports", "Another remark"],
    ]
    crits = parse_from_tables([table])
    assert crits[0].remarks == "A remark"
    assert "Conformance Level" not in crits[0].remarks


def test_bare_status_row_is_not_a_criterion():
    """The Terms/legend page lists every status verbatim; it is not data."""
    tables = [
        [
            ["Supports", "", "The functionality meets the criterion."],
            ["Not Applicable", "", "The criterion is not relevant."],
        ]
    ]
    assert parse_from_tables(tables) == []


def test_google_classroom_multi_component_status_cell():
    """Google Classroom: one row, several component answers in one cell.

    The Conformance Level cell holds a status per reporting target ("Web:",
    "Authoring Tool:"). Requiring the whole cell to be a single status left 37
    of 56 criteria "Not Evaluated". The row's status is the *worst* component
    answer (worst-wins), and the raw status keeps the full multi-part cell --
    which component said what is the evidence.
    """
    row = [
        "1.1.1 Non-text Content (Level A)\nAlso applies to:\nEN 301 549 Criteria\n"
        "● 9.1.1.1 (Web)\n● 11.8.2 (Authoring Tool)",
        "Web: Partially Supports\nAuthoring Tool: Supports",
        "Web: Most non-text content that is presented to the user has a text "
        "alternative that serves the equivalent purpose.",
    ]
    crits = parse_from_tables([[row, row]])
    assert len(crits) == 1
    assert crits[0].normalized_status == "Partially Supports"
    assert crits[0].raw_status == "Web: Partially Supports Authoring Tool: Supports"
    # The remarks cell also opens with a component prefix; it must still be
    # read as remarks, never as the answer.
    assert "Most non-text content" in crits[0].remarks


def test_single_component_cell_keeps_stripped_raw_status():
    """Google Drawings: a lone "Web: Not Applicable" stays as it always was."""
    row = [
        "1.2.1 Audio-only and Video-only (Prerecorded) (Level A)",
        "Web: Not Applicable",
        "Web: Pre-recorded audio-only files are not present.",
    ]
    crits = parse_from_tables([[row, row]])
    assert len(crits) == 1
    assert crits[0].raw_status == "Not Applicable"
    assert crits[0].normalized_status == "Not Applicable"


def test_multi_component_cell_must_be_nothing_but_statuses():
    """Segmentation must never promote prose into a conformance value.

    Real shapes: trailing prose after the last status, a component with no
    answer at all, a review guide's "Clarification:" cells, and the Terms
    legend listing every status without any component prefix. A missing status
    always beats a wrong one.
    """
    rows = [
        [
            "1.1.1 Non-text Content (Level A)",
            "Web: Supports Authoring Tool: Supports See remarks",
            "x",
        ],
        [
            "1.2.1 Audio-only (Prerecorded) (Level A)",
            "Web: Authoring Tool: Supports",
            "y",
        ],
        [
            "1.2.2 Captions (Prerecorded) (Level A)",
            "Clarification: This criterion is asking whether users can tell what "
            "the non-text content is for.",
            "z",
        ],
        [
            "1.2.3 Audio Description (Level A)",
            "Supports Partially Supports Does Not Support",
            "w",
        ],
    ]
    crits = parse_from_tables([rows])
    assert [c.raw_status for c in crits] == ["", "", "", ""]


def test_support_docs_prefix_does_not_collide_with_the_support_status():
    """ "Support Docs:" is a component name, not the "Supports" status."""
    row = [
        "1.1.1 Non-text Content (Level A)",
        "Web: Supports\nSupport Docs: Partially Supports",
        "x",
    ]
    crits = parse_from_tables([[row, row]])
    assert len(crits) == 1
    assert crits[0].normalized_status == "Partially Supports"
    assert crits[0].raw_status == "Web: Supports Support Docs: Partially Supports"


def test_sample_vpat_kerning_split_status_cell():
    """Sample-VPAT.pdf: extraction splits the first letter off words.

    The text layer (and the table cells) arrive as "P artially Supports" /
    "S upports". The heal must recover the status without ever joining words
    that only *look* split.
    """
    rows = [
        [
            "1.1.1 Non-text Content (Level A)",
            "P artially Supports",
            "The site provides sufficient text alternatives for most instances "
            "of non-text content.",
        ],
        [
            "1.3.2 Meaningful Sequence (Level A)",
            "S upports",
            "The site content is presented in a meaningful sequence.",
        ],
    ]
    crits = parse_from_tables([rows])
    assert [c.normalized_status for c in crits] == ["Partially Supports", "Supports"]
    assert crits[0].raw_status == "Partially Supports"


def test_kerning_split_partially_is_never_read_as_supports():
    """Rule 7 pin, transcribed from Sample-VPAT.pdf's text layer.

    Before healing, the same-line status search matched the " Supports" tail
    *inside* "P artially Supports" -- rows 1.1.1 and 1.3.1 were recorded as
    "Supports" when the vendor said "Partially Supports". A confidently wrong
    status is the worst possible outcome.
    """
    text = (
        "1.3.1 Info and Relationships (Level A) P artially Supports Most visual "
        "structure and relationship information is\n"
        "Information, structure, and relationships conveyed through presentation "
        "provided through object information or is available in\n"
    )
    crits = parse_from_text(text, set())
    assert len(crits) == 1
    assert crits[0].normalized_status == "Partially Supports"


def test_heal_only_rejoins_status_words():
    """The heal is a closed-vocabulary repair, not a general spell-fixer."""
    assert heal_kerning_splits("P artially Supports") == "Partially Supports"
    assert heal_kerning_splits("S upports") == "Supports"
    assert heal_kerning_splits("N ot A pplicable") == "Not Applicable"
    # Real prose fragments from the same document must never be joined.
    prose = "A mechanism is available; a user visits the s ite on their webpage"
    assert heal_kerning_splits(prose) == prose
    # An intact status is left exactly as it is.
    assert heal_kerning_splits("Not Applicable") == "Not Applicable"


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
