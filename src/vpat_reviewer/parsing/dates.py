"""Vendor-report-date parsing. Relocated verbatim from the v10 parser."""

from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_date(s: str) -> date | None:
    if not s:
        return None
    s = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
    patterns = [
        (r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", "mname_d_y"),
        (r"(\d{1,2})\s+(\w+)\s+(\d{4})", "d_mname_y"),
        (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "ymd"),
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", "mdy"),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, s, re.IGNORECASE)
        if not m:
            continue
        try:
            if fmt == "mname_d_y":
                mo = MONTHS.get(m.group(1).lower())
                if mo:
                    return date(int(m.group(3)), mo, int(m.group(2)))
            elif fmt == "d_mname_y":
                mo = MONTHS.get(m.group(2).lower())
                if mo:
                    return date(int(m.group(3)), mo, int(m.group(1)))
            elif fmt == "ymd":
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif fmt == "mdy":
                yr = int(m.group(3))
                if yr < 100:
                    yr += 2000
                return date(yr, int(m.group(1)), int(m.group(2)))
        except (ValueError, TypeError):
            continue
    # v9 FIX D: month-year only dates (e.g. "August 2020") have no day number.
    # Convention: treat as the 1st of the month, so outdated-VPAT detection works.
    my = re.search(r"(\w+)\s+(\d{4})\s*$", s.strip(), re.IGNORECASE)
    if my:
        mo = MONTHS.get(my.group(1).lower())
        if mo:
            try:
                return date(int(my.group(2)), mo, 1)
            except (ValueError, TypeError):
                pass
    return None
