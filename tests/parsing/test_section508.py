from vpat_reviewer.parsing.section508 import FPC_TITLES, parse_508_ch6, parse_508_fpc


def test_fpc_from_table():
    tables = [[["302.1 anything", "Supports", "Screen reader works."]]]
    crits = parse_508_fpc(tables, "")
    assert len(crits) == 1
    assert crits[0].criterion_id == "302.1"
    assert crits[0].title == FPC_TITLES["302.1"]  # canonical title, not the cell text
    assert crits[0].section == "508_fpc"
    assert crits[0].normalized_status == "Supports"


def test_fpc_from_table_finds_status_at_any_width():
    """Vendors vary the table width; the 302 rows are found the same way as WCAG rows."""
    for width, status_col in ((3, 1), (5, 2), (8, 3), (9, 3)):
        row = [""] * width
        row[0] = "302.1 Without Vision"
        row[status_col] = "Partially Supports"
        crits = parse_508_fpc([[row]], "")
        assert len(crits) == 1, f"width {width}"
        assert crits[0].normalized_status == "Partially Supports", f"width {width}"


def test_fpc_text_fallback_builds_all_nine():
    text = " ".join(f"{cid} Supports" for cid in FPC_TITLES)
    crits = parse_508_fpc([], text)
    assert {c.criterion_id for c in crits} == set(FPC_TITLES)


def test_fpc_text_fallback_reports_only_what_the_document_states():
    """A document that never mentions a 302 criterion has none to report.

    The fallback used to emit all nine regardless, defaulting to "Not Evaluated",
    which put nine functional performance criteria into documents that were not
    VPATs at all.
    """
    assert parse_508_fpc([], "This document says nothing about 508 at all.") == []

    partial = parse_508_fpc([], "302.1 Supports and 302.4 Does Not Support.")
    assert {c.criterion_id for c in partial} == {"302.1", "302.4"}
    assert all(c.raw_status for c in partial), "a reported row must carry real evidence"


def test_ch6_602_3_orphan_gating():  # v9 FIX H
    tables = [
        [
            ["602.3 (Support Docs)", "See WCAG 2.1 section", ""],  # orphan — must be skipped
            ["602.3 Electronic Support Documentation", "Supports", "Docs accessible."],  # real
        ]
    ]
    crits = parse_508_ch6(tables)
    assert len(crits) == 1
    assert crits[0].criterion_id == "602.3"
    assert "Electronic Support" in crits[0].title
    assert crits[0].normalized_status == "Supports"


def test_ch6_heading_cell_skipped():
    tables = [[["602.1 Something", "heading cell", ""]]]
    assert parse_508_ch6(tables) == []
