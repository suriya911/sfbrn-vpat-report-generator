"""Extractor registry — picks an adapter by file extension.

To support a new format: implement an :class:`Extractor` and add it to
``_EXTRACTORS`` below. Nothing else in the codebase needs to change.
"""

from __future__ import annotations

from pathlib import Path

from vpat_reviewer.extraction.base import Extractor, RawDocument
from vpat_reviewer.extraction.docx import DocxExtractor
from vpat_reviewer.extraction.pdf import PdfExtractor
from vpat_reviewer.extraction.txt import TxtExtractor


class UnsupportedFormatError(ValueError):
    """Raised when no registered extractor handles a file's extension."""

    def __init__(self, ext: str) -> None:
        super().__init__(f"Unsupported file type: {ext}")
        self.ext = ext


_EXTRACTORS: list[Extractor] = [PdfExtractor(), DocxExtractor(), TxtExtractor()]


def supported_extensions() -> tuple[str, ...]:
    return tuple(ext for e in _EXTRACTORS for ext in e.extensions)


def get_extractor(path: str) -> Extractor | None:
    ext = Path(path).suffix.lower()
    if ext == ".doc":  # legacy: treat .doc like .docx
        ext = ".docx"
    for e in _EXTRACTORS:
        if ext in e.extensions:
            return e
    return None


def extract(path: str) -> RawDocument:
    """Extract a file to a :class:`RawDocument`, or raise ``UnsupportedFormatError``."""
    extractor = get_extractor(path)
    if extractor is None:
        raise UnsupportedFormatError(Path(path).suffix.lower())
    return extractor.extract(path)
