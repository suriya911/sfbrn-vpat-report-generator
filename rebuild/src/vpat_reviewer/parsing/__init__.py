"""Parsing: turn a :class:`RawDocument` (text + tables) into a ``VPATDocument``.

Pure with respect to files — everything here operates on already-extracted text
and tables, so it is fully testable without a real PDF/DOCX. The regex logic is
relocated verbatim from the v10 parser; every ``v9 FIX`` comment marks a
behavior that is pinned by a regression test.
"""

from vpat_reviewer.parsing.document import parse_document, parse_vpat

__all__ = ["parse_document", "parse_vpat"]
