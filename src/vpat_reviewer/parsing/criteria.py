"""WCAG criterion-row parsing (from tables, with a text fallback).

Table parsing (PDF/DOCX) is unchanged from v10. The text fallback was hardened so
plain-text / HTML-derived VPATs (real vendor ACRs saved as .txt) parse and score:

* level written as ``(Level AA 2.1 only)`` / ``(WCAG 2.1)`` not just ``(Level AA)``;
* conformance prefixed with a target column, e.g. ``Web: Supports``;
* status on the SAME line as the criterion (tab / dash / colon separated), or many
  lines below it after EN 301 549 cross-references.

The criterion ID uniquely determines its WCAG level, so ``WCAG_LEVELS`` assigns
the level authoritatively and lets the text parser tell a real WCAG row apart from
an EN 301 549 reference (``9.1.1.1`` …) that shares the N.N.N shape.
"""

from __future__ import annotations

import re

from vpat_reviewer.domain.models import VPATCriterion
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.extraction.base import Table
from vpat_reviewer.parsing.text_cleanup import clean_extracted_text

CRIT_RE = re.compile(r"(\d+\.\d+\.\d+)\s+(.+?)\s*\(Level\s+(A{1,3})\b", re.IGNORECASE)
STATUS_RE = re.compile(
    r"^(Supports\s+with\s+Exceptions|Partially\s+Supports?|Does\s+Not\s+Supports?|"
    r"Not\s+Applicable|Not\s+Evaluated|Supports?|Supported|Support\b)",
    re.IGNORECASE,
)

WCAG_LEVELS: dict[str, str] = {
    "1.1.1": "A",
    "1.2.1": "A",
    "1.2.2": "A",
    "1.2.3": "A",
    "1.3.1": "A",
    "1.3.2": "A",
    "1.3.3": "A",
    "1.4.1": "A",
    "1.4.2": "A",
    "2.1.1": "A",
    "2.1.2": "A",
    "2.1.4": "A",
    "2.2.1": "A",
    "2.2.2": "A",
    "2.3.1": "A",
    "2.4.1": "A",
    "2.4.2": "A",
    "2.4.3": "A",
    "2.4.4": "A",
    "2.5.1": "A",
    "2.5.2": "A",
    "2.5.3": "A",
    "2.5.4": "A",
    "3.1.1": "A",
    "3.2.1": "A",
    "3.2.2": "A",
    "3.3.1": "A",
    "3.3.2": "A",
    "4.1.1": "A",
    "4.1.2": "A",
    "1.2.4": "AA",
    "1.2.5": "AA",
    "1.3.4": "AA",
    "1.3.5": "AA",
    "1.4.3": "AA",
    "1.4.4": "AA",
    "1.4.5": "AA",
    "1.4.10": "AA",
    "1.4.11": "AA",
    "1.4.12": "AA",
    "1.4.13": "AA",
    "2.4.5": "AA",
    "2.4.6": "AA",
    "2.4.7": "AA",
    "2.4.11": "AA",
    "2.5.7": "AA",
    "2.5.8": "AA",
    "3.1.2": "AA",
    "3.2.3": "AA",
    "3.2.4": "AA",
    "3.2.6": "AA",
    "3.3.3": "AA",
    "3.3.4": "AA",
    "3.3.7": "AA",
    "3.3.8": "AA",
    "4.1.3": "AA",
    "1.2.6": "AAA",
    "1.2.7": "AAA",
    "1.2.8": "AAA",
    "1.2.9": "AAA",
    "1.3.6": "AAA",
    "1.4.6": "AAA",
    "1.4.7": "AAA",
    "1.4.8": "AAA",
    "1.4.9": "AAA",
    "2.1.3": "AAA",
    "2.2.3": "AAA",
    "2.2.4": "AAA",
    "2.2.5": "AAA",
    "2.2.6": "AAA",
    "2.3.2": "AAA",
    "2.3.3": "AAA",
    "2.4.8": "AAA",
    "2.4.9": "AAA",
    "2.4.10": "AAA",
    "2.4.12": "AAA",
    "2.4.13": "AAA",
    "2.5.5": "AAA",
    "2.5.6": "AAA",
    "3.1.3": "AAA",
    "3.1.4": "AAA",
    "3.1.5": "AAA",
    "3.1.6": "AAA",
    "3.2.5": "AAA",
    "3.3.5": "AAA",
    "3.3.6": "AAA",
    "3.3.9": "AAA",
}

_STATUS_PREFIX_RE = re.compile(
    r"^(?:Web|Software|Hardware|Open|Closed|Both|Authoring\s*Tool|Documentation)"
    r"(?:\s*\([^)]*\))?\s*:\s*",
    re.IGNORECASE,
)
_TEXT_ID_RE = re.compile(r"^\s*(\d+\.\d+\.\d+)\b(.*)$")
_TEXT_LEVEL_RE = re.compile(r"\(\s*(?:Level|WCAG)\s+(?:[\d.]+\s+)?(A{1,3})\b", re.IGNORECASE)
_LEVEL_CUT_RE = re.compile(r"\(\s*(?:Level|WCAG)\b", re.IGNORECASE)
# A conformance value preceded by a cell/token boundary (tab, pipe, dash, colon).
_STATUS_ANYWHERE_RE = re.compile(
    r"(?:[\s|\t—–:-])\s*"
    r"(Supports\s+with\s+Exceptions|Partially\s+Supports?|Does\s+Not\s+Supports?|"
    r"Not\s+Applicable|Not\s+Evaluated|Supported|Supports?)\b",
    re.IGNORECASE,
)


def clean_criterion_title(title: str) -> str:
    """Remove cross-reference boilerplate from criterion titles."""
    title = re.sub(r"\s+Also\s+applies\s+to\s*:.*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+Revised\s+Section\s+508.*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+EN\s+301\s+549.*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+\d{3}\s+\(Web\).*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    return title.strip()


def clean_remarks(remarks: str) -> str:
    if not remarks:
        return ""
    r = re.sub(r"^Remark\s*s?\s*:", "", remarks, flags=re.IGNORECASE).strip()
    r = clean_extracted_text(r)
    r = re.sub(r'"Voluntary Product[^"]*"[^\n]*\n?', "", r)
    r = re.sub(r"service marks of[^\n]*\n?", "", r)
    return r.strip()


def parse_from_tables(tables: list[Table]) -> list[VPATCriterion]:
    criteria: list[VPATCriterion] = []
    seen: set[str] = set()

    for table in tables:
        if not table or len(table) < 2:
            continue

        col_layout = None
        for row in table:
            if not row:
                continue
            cell0 = str(row[0] or "").strip()
            if CRIT_RE.search(cell0):
                if len(row) >= 9:
                    c3 = str(row[3] or "").strip() if len(row) > 3 else ""
                    c6 = str(row[6] or "").strip() if len(row) > 6 else ""
                    col_layout = "9col" if (c3 or c6) else "3col"
                elif len(row) >= 3:
                    col_layout = "3col"
                break
        if col_layout is None:
            col_layout = "3col"

        for row in table:
            if not row:
                continue
            cell0 = str(row[0] or "").strip()
            m = CRIT_RE.search(cell0)
            if not m:
                continue

            crit_id = m.group(1)
            if crit_id in seen:
                continue
            seen.add(crit_id)

            title = clean_criterion_title(m.group(2).strip())
            level = WCAG_LEVELS.get(crit_id, m.group(3).upper())

            if col_layout == "9col":
                raw_status = str(row[3] or "").strip() if len(row) > 3 else ""
                remarks_raw = str(row[6] or "").strip() if len(row) > 6 else ""
            else:
                raw_status = str(row[1] or "").strip() if len(row) > 1 else ""
                remarks_raw = str(row[2] or "").strip() if len(row) > 2 else ""

            if remarks_raw and CRIT_RE.match(remarks_raw.strip()):
                remarks_raw = ""

            criteria.append(
                VPATCriterion(
                    criterion_id=crit_id,
                    title=title,
                    level=level,
                    raw_status=raw_status,
                    normalized_status=normalize_status(raw_status),
                    remarks=clean_remarks(remarks_raw),
                )
            )

    return criteria


def _status_in(segment: str) -> str:
    seg = _STATUS_PREFIX_RE.sub("", segment.strip())
    m = STATUS_RE.match(seg)
    return m.group(0).strip() if m else ""


def _is_criterion_line(raw_line: str):
    m = _TEXT_ID_RE.match(raw_line)
    if not m:
        return None
    crit_id, rest = m.group(1), m.group(2)
    if WCAG_LEVELS.get(crit_id) or _TEXT_LEVEL_RE.search(rest):
        return crit_id, rest
    return None


def parse_from_text(text: str, seen_ids: set[str]) -> list[VPATCriterion]:
    criteria: list[VPATCriterion] = []
    lines = text.split("\n")
    n = len(lines)
    i = 0
    while i < n:
        hit = _is_criterion_line(lines[i])
        if hit is None:
            i += 1
            continue

        crit_id, rest = hit
        if crit_id in seen_ids:
            i += 1
            continue
        seen_ids.add(crit_id)

        inline = _TEXT_LEVEL_RE.search(rest)
        level = WCAG_LEVELS.get(crit_id) or (inline.group(1).upper() if inline else "")

        raw_status = ""
        remarks: list[str] = []

        # (1) status on the SAME line (tabular / dash / colon separated rows).
        sm = _STATUS_ANYWHERE_RE.search(rest)
        cut = _LEVEL_CUT_RE.search(rest)
        title_end = sm.start() if sm else (cut.start() if cut else len(rest))
        title = clean_criterion_title(rest[:title_end].strip())
        title = re.sub(r"\(\s*(?:Level|WCAG)[^)]*\)\s*$", "", title).strip()
        if sm:
            raw_status = sm.group(1)
            tail = rest[sm.end() :].strip(" \t:|-—–")
            if tail:
                remarks.append(_STATUS_PREFIX_RE.sub("", tail))

        # (2) otherwise scan following lines: skip EN 301 549 refs / boilerplate,
        #     grab the first conformance value, then collect remarks until the next
        #     WCAG criterion row.
        j = i + 1
        boundary = None
        while j < n and j < i + 60:
            if _is_criterion_line(lines[j]) is not None:
                boundary = j
                break
            cand = lines[j].strip()
            if cand:
                if not raw_status:
                    st = _status_in(cand)
                    if st:
                        raw_status = st
                        j += 1
                        continue
                else:
                    body = _STATUS_PREFIX_RE.sub("", cand)
                    if body and not re.match(
                        r"^(Also\s+applies|EN\s+301|Revised\s+Section|\d+\.\d+|5\d{2}\b|Notes?\s*:)",
                        body,
                        re.IGNORECASE,
                    ):
                        remarks.append(
                            re.sub(r"^Remark\s*s?\s*:\s*", "", body, flags=re.IGNORECASE)
                        )
            j += 1

        criteria.append(
            VPATCriterion(
                criterion_id=crit_id,
                title=title,
                level=level,
                raw_status=raw_status,
                normalized_status=normalize_status(raw_status),
                remarks=clean_remarks(" ".join(r for r in remarks if r)),
            )
        )
        i = boundary if boundary is not None else j
    return criteria
