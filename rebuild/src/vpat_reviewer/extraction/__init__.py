"""Extraction: turn a file into a :class:`RawDocument` (text + tables).

Adapters wrap third-party readers (pdfplumber, python-docx) so the parsing layer
never touches a file or a library. Add a new input format by writing an
``Extractor`` and registering it in ``registry.py``.
"""

from vpat_reviewer.extraction.base import Extractor, RawDocument, Table
from vpat_reviewer.extraction.registry import (
    UnsupportedFormatError,
    extract,
    get_extractor,
    supported_extensions,
)

__all__ = [
    "Extractor",
    "RawDocument",
    "Table",
    "UnsupportedFormatError",
    "extract",
    "get_extractor",
    "supported_extensions",
]
