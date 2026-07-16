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

    def __init__(self, ext: str, hint: str = "") -> None:
        message = f"Unsupported file type: {ext}"
        if hint:
            message = f"{message}. {hint}"
        super().__init__(message)
        self.ext = ext
        self.hint = hint


# Extensions we recognise but genuinely cannot read, mapped to what the user
# should do about it. Better to say so than to hand back an empty document.
_REJECTED: dict[str, str] = {
    ".doc": (
        "This is the legacy Word format (Word 97-2003), which is a different "
        "file format from .docx and cannot be read. Open it in Word and use "
        "Save As to convert it to .docx, then try again."
    ),
}

_EXTRACTORS: list[Extractor] = [PdfExtractor(), DocxExtractor(), TxtExtractor()]


def supported_extensions() -> tuple[str, ...]:
    return tuple(ext for e in _EXTRACTORS for ext in e.extensions)


def get_extractor(path: str) -> Extractor | None:
    ext = Path(path).suffix.lower()
    if ext in _REJECTED:
        return None
    for e in _EXTRACTORS:
        if ext in e.extensions:
            return e
    return None


def extract(path: str) -> RawDocument:
    """Extract a file to a :class:`RawDocument`, or raise ``UnsupportedFormatError``."""
    extractor = get_extractor(path)
    if extractor is None:
        ext = Path(path).suffix.lower()
        raise UnsupportedFormatError(ext, _REJECTED.get(ext, ""))
    return extractor.extract(path)
