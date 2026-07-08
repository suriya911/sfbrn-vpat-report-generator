"""Detect which accessibility standards a VPAT declares. Verbatim from v10."""

from __future__ import annotations

import re


def detect_standards(text: str) -> list[str]:
    """Detect standards, supporting both 'WCAG' and the spelled-out name."""
    prefix = r"(?:WCAG|Web\s+Content\s+Accessibility\s+Guidelines)\s*"
    checks = [
        (prefix + r"2\.0.*?Level\s*A(?!\s*A)", "WCAG 2.0 Level A"),
        (prefix + r"2\.0.*?Level\s*AA\b", "WCAG 2.0 Level AA"),
        (prefix + r"2\.1.*?Level\s*A(?!\s*A)", "WCAG 2.1 Level A"),
        (prefix + r"2\.1.*?Level\s*AA\b", "WCAG 2.1 Level AA"),
        (prefix + r"2\.2.*?Level\s*A(?!\s*A)", "WCAG 2.2 Level A"),
        (prefix + r"2\.2.*?Level\s*AA\b", "WCAG 2.2 Level AA"),
        (r"(?:Section\s*508|Revised\s*508)", "Section 508 (Revised 2017)"),
        (r"EN\s*301\s*549", "EN 301 549"),
    ]
    standards: list[str] = []
    seen: set[str] = set()
    for pat, label in checks:
        if label not in seen and re.search(pat, text, re.IGNORECASE | re.DOTALL):
            standards.append(label)
            seen.add(label)
    return standards
