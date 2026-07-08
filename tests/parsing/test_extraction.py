from pathlib import Path

import pytest

from vpat_reviewer.extraction import (
    RawDocument,
    UnsupportedFormatError,
    extract,
    get_extractor,
    supported_extensions,
)
from vpat_reviewer.extraction.docx import DocxExtractor
from vpat_reviewer.extraction.pdf import PdfExtractor
from vpat_reviewer.extraction.txt import TxtExtractor


def test_get_extractor_by_extension():
    assert isinstance(get_extractor("a.pdf"), PdfExtractor)
    assert isinstance(get_extractor("a.docx"), DocxExtractor)
    assert isinstance(get_extractor("a.doc"), DocxExtractor)  # legacy: .doc -> docx
    assert isinstance(get_extractor("a.txt"), TxtExtractor)
    assert get_extractor("a.xlsx") is None


def test_supported_extensions():
    exts = supported_extensions()
    assert ".pdf" in exts and ".docx" in exts and ".txt" in exts


def test_extract_unsupported_raises():
    with pytest.raises(UnsupportedFormatError):
        extract("file.xlsx")


def test_txt_extraction(tmp_path: Path):
    p = tmp_path / "a.txt"
    p.write_text("hello world", encoding="utf-8")
    raw = extract(str(p))
    assert raw.text == "hello world"
    assert raw.tables == []


def test_txt_extraction_missing_file_is_empty(tmp_path: Path):
    raw = extract(str(tmp_path / "nope.txt"))
    assert raw.is_empty


def test_raw_document_is_empty():
    assert RawDocument("   \n ", []).is_empty
    assert not RawDocument("x", []).is_empty
