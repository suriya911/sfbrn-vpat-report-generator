from pathlib import Path

from vpat_reviewer.domain.scoring import compliance_score
from vpat_reviewer.extraction.base import RawDocument
from vpat_reviewer.parsing.document import parse_document, parse_vpat


def test_parse_document_integration():
    text = (
        "Name of Product/Version: DemoTool 3.0\n"
        "Vendor: Instructure\n"
        "Conforms to WCAG 2.1 Level AA and Section 508.\n"
    )
    tables = [
        [
            ["Criteria", "Conformance Level", "Remarks"],
            ["1.4.3 Contrast (Minimum) (Level AA)", "Supports", ""],
            ["1.4.4 Resize Text (Level AA)", "Partially Supports", "Resizes to 150%."],
            ["2.1.1 Keyboard (Level A)", "Supports", ""],
        ]
    ]
    doc = parse_document(RawDocument(text, tables))
    assert doc.product_name == "DemoTool"
    assert doc.product_version == "3.0"
    assert doc.vendor_name == "Instructure"
    assert "WCAG 2.1 Level AA" in doc.standards_reviewed
    # parse_vpat also synthesizes the 9 Section 508 FPC rows (level=""); assert the
    # WCAG rows specifically. FPC rows sit outside the graded levels and don't score.
    wcag = [c for c in doc.criteria if c.section == "wcag"]
    assert len(wcag) == 3

    info = compliance_score(doc)  # cumulative A+AA: 2 of 3 supported
    assert info["total"] == 3 and info["supported"] == 2 and info["score"] == 67


def test_parse_document_outdated_detection():
    doc = parse_document(RawDocument("Report Date: January 2015\n", []))
    assert doc.is_outdated
    assert "months old" in doc.outdated_note


def test_parse_vpat_txt(tmp_path: Path):
    p = tmp_path / "vpat.txt"
    p.write_text(
        "Name of Product/Version: TxtTool 1.0\n"
        "1.4.3 Contrast (Minimum) (Level AA)\nSupports\n"
        "2.4.7 Focus Visible (Level AA)\nDoes Not Support\n",
        encoding="utf-8",
    )
    doc = parse_vpat(str(p))
    assert doc.product_name == "TxtTool"
    wcag = [c for c in doc.criteria if c.section == "wcag"]
    assert len(wcag) == 2
    assert compliance_score(doc)["score"] == 50


def test_parse_vpat_unsupported_records_warning():
    doc = parse_vpat("mystery.xlsx")
    assert any("Unsupported file type" in w for w in doc.parse_warnings)


def test_parse_vpat_empty_file_records_warning(tmp_path: Path):
    p = tmp_path / "empty.txt"
    p.write_text("   ", encoding="utf-8")
    doc = parse_vpat(str(p))
    assert any("No text could be extracted" in w for w in doc.parse_warnings)
