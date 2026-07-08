"""Text cleanup helpers — strip watermarks/boilerplate that leak into extraction."""

from __future__ import annotations

import re

# Watermark/footer text that leaks into extracted text.
WATERMARK_PATTERNS = [
    re.compile(
        r'"Voluntary Product Accessibility Template"[^\n]*\n[^\n]*Page\s+\d+\s+of\s+\d+',
        re.IGNORECASE,
    ),
    re.compile(r"Page\s+\d+\s+of\s+\d+", re.IGNORECASE),
    re.compile(r"_{10,}"),  # long underscores (horizontal rules)
]


def clean_extracted_text(text: str) -> str:
    """Remove watermarks, page numbers, and boilerplate from extracted text."""
    for pat in WATERMARK_PATTERNS:
        text = pat.sub(" ", text)
    return text


def is_blank_or_garbage(text: str) -> bool:
    """True if a field value is blank, a VPAT section header, or garbage to drop."""
    if not text or not text.strip():
        return True
    t = text.strip().lower()
    garbage_starts = [
        "contact information",
        "notes:",
        "note:",
        "see wcag",
        "heading cell",
        "voluntary product",
        '"voluntary',
        "this report",
        "the testing",
        "remark",
        "n/a",
    ]
    for g in garbage_starts:
        if t.startswith(g):
            return True
    # Very short but non-meaningful.
    return len(t) < 3
