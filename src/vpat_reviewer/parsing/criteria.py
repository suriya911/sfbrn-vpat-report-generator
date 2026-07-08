"""WCAG criterion-row parsing (from tables, with a text fallback). Verbatim from v10."""

from __future__ import annotations

import re

from vpat_reviewer.domain.models import VPATCriterion
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.extraction.base import Table
from vpat_reviewer.parsing.text_cleanup import clean_extracted_text

CRIT_RE = re.compile(r"(\d+\.\d+\.\d+)\s+(.+?)\s*\(Level\s+(A{1,3})\)", re.IGNORECASE)
STATUS_RE = re.compile(
    r"^(Supports\s+with\s+Exceptions|Partially\s+Supports?|Does\s+Not\s+Supports?|"
    r"Not\s+Applicable|Not\s+Evaluated|Supports?|Supported|Support\b)",
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

        # Detect column layout.
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
            level = m.group(3).upper()

            if col_layout == "9col":
                raw_status = str(row[3] or "").strip() if len(row) > 3 else ""
                remarks_raw = str(row[6] or "").strip() if len(row) > 6 else ""
            else:
                raw_status = str(row[1] or "").strip() if len(row) > 1 else ""
                remarks_raw = str(row[2] or "").strip() if len(row) > 2 else ""

            # Guard against continuation rows being mistaken for remarks.
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


def parse_from_text(text: str, seen_ids: set[str]) -> list[VPATCriterion]:
    criteria: list[VPATCriterion] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = CRIT_RE.search(line)
        if m:
            crit_id = m.group(1)
            if crit_id in seen_ids:
                i += 1
                continue
            seen_ids.add(crit_id)

            title = clean_criterion_title(m.group(2).strip())
            level = m.group(3).upper()

            raw_status, remarks_lines = "", []
            j = i + 1
            found_status = False
            in_remarks = False

            while j < min(i + 25, len(lines)):
                candidate = lines[j].strip()
                if not found_status:
                    sm = STATUS_RE.match(candidate)
                    if sm:
                        raw_status = sm.group(0)
                        found_status = True
                        j += 1
                        continue
                if found_status:
                    if re.match(r"^Remark", candidate, re.IGNORECASE):
                        in_remarks = True
                        j += 1
                        continue
                    if in_remarks:
                        if CRIT_RE.search(candidate):
                            break
                        remarks_lines.append(candidate)
                    elif CRIT_RE.search(candidate):
                        break
                j += 1

            remarks = " ".join(r for r in remarks_lines if r).strip()
            criteria.append(
                VPATCriterion(
                    criterion_id=crit_id,
                    title=title,
                    level=level,
                    raw_status=raw_status,
                    normalized_status=normalize_status(raw_status),
                    remarks=clean_remarks(remarks),
                )
            )
            i = j
        else:
            i += 1
    return criteria
