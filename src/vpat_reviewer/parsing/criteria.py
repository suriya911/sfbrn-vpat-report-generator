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
from typing import NamedTuple

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

# A cell holds a conformance value only if the WHOLE cell is one, once a target
# prefix ("Web:") is stripped and wrapping is undone. Anchoring both ends is what
# makes it safe to go looking for the status column instead of trusting an index:
# a remarks cell that merely opens with "Supports the criterion when..." must not
# be mistaken for the answer.
_STRICT_STATUS_RE = re.compile(
    r"(?:Supports\s+with\s+Exceptions|Partially\s+Supports?|Does\s+Not\s+Supports?|"
    r"Does\s+Not\s+Apply|Not\s+Applicable|Not\s+Evaluated|Supported|Supports?|N/?A)",
    re.IGNORECASE,
)
# Cross-references to other standards ride inside the criteria cell. Everything
# from here on describes a *different* standard's clause, so cut it off before
# looking for the WCAG id -- otherwise an EN 301 549 ref can be read as the row.
_CROSSREF_CUT_RE = re.compile(r"\s*Also\s+applies\s+to\s*:", re.IGNORECASE)

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
    # 3.2.6 and 3.3.7 are new in WCAG 2.2 and are Level A, not AA. They were
    # listed as AA below until July 2026, and because this table overrides the
    # vendor's own stated level, both were promoted into the AA denominator --
    # silently changing the score of every WCAG 2.2 report.
    "3.2.6": "A",
    "3.3.1": "A",
    "3.3.2": "A",
    "3.3.7": "A",
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
    "3.3.3": "AA",
    "3.3.4": "AA",
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
    """Remove cross-reference boilerplate and source links from criterion titles."""
    title = re.sub(r"\s+Also\s+applies\s+to\s*:.*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+Revised\s+Section\s+508.*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+EN\s+301\s+549.*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+\d{3}\s+\(Web\).*$", "", title, flags=re.IGNORECASE | re.DOTALL)
    # Some templates (Canvas) inline the W3C definition link after the name.
    title = re.sub(r"\(\s*https?://[^)]*\)", "", title)
    title = re.sub(r"https?://\S+", "", title)
    return re.sub(r"\s{2,}", " ", title).strip()


def _flatten(cell: object) -> str:
    """A cell's text as one line.

    Table cells wrap: a criterion name, its link, and "(Level A)" routinely land
    on three lines of the same cell, and "Not Applicable" arrives as
    "Not\\nApplicable". Matching against the wrapped form is why whole documents
    silently failed to parse.
    """
    return re.sub(r"\s+", " ", str(cell or "")).strip()


def _denoise(text: str) -> str:
    """Drop characters a conformance value can never contain.

    Page overlays (a Box preview watermark, in iCIMS' case) are stamped across
    the page, so their characters fall inside a cell's bounding box and
    interleave with the real text: "Not Applicable" arrives as "Not Applicab2le".
    Conformance values are alphabetic, so the noise can simply be removed --
    *removed*, not replaced with a space, which would split the word instead.
    """
    return re.sub(r"\s{2,}", " ", re.sub(r"[^A-Za-z/\s]", "", text)).strip()


def _cell_status(cell: object) -> str:
    """The conformance value this cell holds, or "" if it is not a status cell."""
    text = _STATUS_PREFIX_RE.sub("", _flatten(cell))
    if text and _STRICT_STATUS_RE.fullmatch(text):
        return text
    # Second pass for overlay-polluted cells. Still a full-cell match, so prose
    # cannot be mistaken for an answer -- only noise is forgiven.
    cleaned = _denoise(text)
    return cleaned if cleaned and _STRICT_STATUS_RE.fullmatch(cleaned) else ""


class RowStatus(NamedTuple):
    """What a table row says, and where it said it."""

    status: str = ""
    remarks: str = ""
    remarks_col: int = -1


def find_row_status(row: list[str | None]) -> RowStatus:
    """Locate the conformance value and its remarks by inspecting the row.

    Vendors put the status in whatever column their template chose -- observed
    widths are 3, 5, 8 and 9, with the status at index 1, 2 or 3. Rather than
    guess from the row width (which silently misread three of the six real VPATs
    in docs/completed_forms), find the cell that *is* a status, then take the
    first substantive cell after it as the remarks.

    The remarks column index comes back too, so a caller can follow the same
    column down through any continuation rows (see ``parse_from_tables``).
    """
    for i in range(1, len(row)):
        status = _cell_status(row[i])
        if not status:
            continue
        for j in range(i + 1, len(row)):
            text = str(row[j] or "").strip()
            if text and not _cell_status(row[j]):
                return RowStatus(status, _STATUS_PREFIX_RE.sub("", text), j)
        return RowStatus(status, "", -1)
    return RowStatus()


def _is_header_row(row: list[str | None]) -> bool:
    """The ITI column headers, which repeat on every page of a long table."""
    joined = " ".join(_flatten(c) for c in row).lower()
    return "remarks and explanations" in joined or "conformance level" in joined


def clean_remarks(remarks: str) -> str:
    if not remarks:
        return ""
    r = re.sub(r"^Remark\s*s?\s*:", "", remarks, flags=re.IGNORECASE).strip()
    r = clean_extracted_text(r)
    r = re.sub(r'"Voluntary Product[^"]*"[^\n]*\n?', "", r)
    r = re.sub(r"service marks of[^\n]*\n?", "", r)
    return r.strip()


def _absorb_continuation(
    current: VPATCriterion | None, remarks_col: int, row: list[str | None]
) -> None:
    """Append a wrapped remarks line to the criterion it belongs to.

    Vendors whose remarks run long (Atrium devotes a page to each criterion)
    emit one table row per *line* of the cell: the first carries the criterion,
    its status and the opening line, and each row after it holds nothing but the
    next line in the remarks column. Read row-by-row, that keeps the first line
    and discards the substance -- which is the part a reviewer actually needs.

    A row only counts as a continuation if it names no criterion and gives no
    status, so a real row is never folded into its predecessor.
    """
    if current is None or remarks_col < 0 or remarks_col >= len(row):
        return
    if find_row_status(row).status:
        return
    text = str(row[remarks_col] or "").strip()
    if not text:
        return
    fragment = clean_remarks(_STATUS_PREFIX_RE.sub("", text))
    if fragment:
        current.remarks = f"{current.remarks} {fragment}".strip()


def parse_from_tables(tables: list[Table]) -> list[VPATCriterion]:
    """Parse criterion rows out of extracted tables.

    Column positions are resolved per row rather than sniffed once per table:
    real vendor templates mix widths, and a table-wide guess misreads every row
    that does not match it. See ``_find_status``.
    """
    criteria: list[VPATCriterion] = []
    seen: set[str] = set()

    for table in tables:
        if not table or len(table) < 2:
            continue

        # A long remarks cell can be broken across several table rows, each
        # carrying only the next line of prose. Those rows belong to the
        # criterion above them, so keep hold of it.
        current: VPATCriterion | None = None
        current_col = -1

        for row in table:
            if not row:
                continue
            if _is_header_row(row):
                current = None  # a repeated header ends the previous row
                continue

            # Cut cross-references first so an EN 301 549 clause can never be
            # mistaken for this row's criterion.
            cell0 = _CROSSREF_CUT_RE.split(_flatten(row[0]))[0]
            m = CRIT_RE.search(cell0)
            if not m:
                _absorb_continuation(current, current_col, row)
                continue

            crit_id = m.group(1)
            if crit_id in seen:
                current = None  # do not hang later prose off a row we dropped
                continue
            seen.add(crit_id)

            found = find_row_status(row)
            remarks_raw = found.remarks
            if remarks_raw and CRIT_RE.match(remarks_raw.strip()):
                remarks_raw = ""

            criterion = VPATCriterion(
                criterion_id=crit_id,
                title=clean_criterion_title(m.group(2).strip()),
                level=WCAG_LEVELS.get(crit_id, m.group(3).upper()),
                raw_status=found.status,
                normalized_status=normalize_status(found.status),
                remarks=clean_remarks(remarks_raw),
            )
            criteria.append(criterion)
            current, current_col = criterion, found.remarks_col

    return criteria


def _status_in(segment: str) -> str:
    seg = _STATUS_PREFIX_RE.sub("", segment.strip())
    m = STATUS_RE.match(seg)
    return m.group(0).strip() if m else ""


def _is_criterion_line(raw_line: str) -> tuple[str, str] | None:
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
