from vpat_reviewer.parsing.section508 import FPC_TITLES, parse_508_ch6, parse_508_fpc


def test_fpc_from_table():
    tables = [[["302.1 anything", "Supports", "Screen reader works."]]]
    crits = parse_508_fpc(tables, "")
    assert len(crits) == 1
    assert crits[0].criterion_id == "302.1"
    assert crits[0].title == FPC_TITLES["302.1"]  # canonical title, not the cell text
    assert crits[0].section == "508_fpc"
    assert crits[0].normalized_status == "Supports"


def test_fpc_text_fallback_builds_all_nine():
    text = " ".join(f"{cid} Supports" for cid in FPC_TITLES)
    crits = parse_508_fpc([], text)
    assert {c.criterion_id for c in crits} == set(FPC_TITLES)


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
