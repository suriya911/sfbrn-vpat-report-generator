"""Section 508 parsing: functional performance criteria (302.x) and Chapter 6
(602/603.x). Relocated verbatim from the v10 parser.
"""

from __future__ import annotations

import re

from vpat_reviewer.domain.models import VPATCriterion
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.extraction.base import Table
from vpat_reviewer.parsing.criteria import clean_remarks, find_row_status


def _is_heading_row(row: list[str | None]) -> bool:
    """Some VPAT tools mark section headers with a literal "heading cell" value.

    Checked across the whole row rather than at a fixed index, because the
    conformance column is not in a fixed place -- and because the marker is not
    a conformance value, so the status finder correctly ignores it.
    """
    return any("heading cell" in str(cell or "").lower() for cell in row)


FPC_TITLES = {
    "302.1": "Without Vision",
    "302.2": "With Limited Vision",
    "302.3": "Without Perception of Color",
    "302.4": "Without Hearing",
    "302.5": "With Limited Hearing",
    "302.6": "Without Speech",
    "302.7": "With Limited Manipulation",
    "302.8": "With Limited Reach and Strength",
    "302.9": "With Limited Language, Cognitive, and Learning Abilities",
}


def parse_508_fpc(tables: list[Table], text: str) -> list[VPATCriterion]:
    criteria: list[VPATCriterion] = []
    seen: set[str] = set()
    fpc_re = re.compile(r"^(302\.\d)\s*(.*)", re.IGNORECASE)

    for table in tables:
        for row in table:
            if not row:
                continue
            cell0 = str(row[0] or "").strip()
            m = fpc_re.match(cell0)
            if not m:
                continue
            cid = m.group(1)
            if cid in seen:
                continue
            if _is_heading_row(row):
                continue
            seen.add(cid)
            title = FPC_TITLES.get(cid, m.group(2).strip())
            found = find_row_status(row)

            criteria.append(
                VPATCriterion(
                    criterion_id=cid,
                    title=title,
                    level="",
                    raw_status=found.status,
                    normalized_status=normalize_status(found.status),
                    remarks=clean_remarks(found.remarks),
                    section="508_fpc",
                )
            )

    # Text fallback for documents whose FPC section is prose rather than a table.
    #
    # This reports a criterion only where the document actually states one. It
    # used to emit all nine rows unconditionally, defaulting the status to
    # "Not Evaluated" -- so every document, including files that were not VPATs
    # at all, came back carrying nine functional performance criteria the vendor
    # had never written. A row with no evidence behind it is not a finding.
    if not criteria:
        for cid, ctitle in FPC_TITLES.items():
            if cid in seen:
                continue
            pat = re.compile(
                re.escape(cid) + r".{0,200}?"
                r"(Supports\s+with\s+Exceptions|Partially\s+Supports?|Does\s+Not\s+Supports?|"
                r"Not\s+Applicable|Not\s+Evaluated|Supports?)",
                re.IGNORECASE | re.DOTALL,
            )
            m2 = pat.search(text)
            if not m2:
                continue
            seen.add(cid)
            raw_status = m2.group(1)
            chunk = text[m2.end() : m2.end() + 500]
            stop = re.search(r"302\.\d|Chapter\s+[456]", chunk)
            remarks_text = re.sub(r"\s+", " ", chunk[: stop.start() if stop else 300]).strip()
            criteria.append(
                VPATCriterion(
                    criterion_id=cid,
                    title=ctitle,
                    level="",
                    raw_status=raw_status,
                    normalized_status=normalize_status(raw_status),
                    remarks=clean_remarks(remarks_text),
                    section="508_fpc",
                )
            )

    return criteria


def parse_508_ch6(tables: list[Table]) -> list[VPATCriterion]:
    criteria: list[VPATCriterion] = []
    seen: set[str] = set()
    ch6_re = re.compile(r"^(60[23]\.\d)\s*(.*)", re.IGNORECASE)

    for table in tables:
        for row in table:
            if not row:
                continue
            cell0 = str(row[0] or "").strip()
            m = ch6_re.match(cell0)
            if not m:
                continue
            cid = m.group(1)
            title = m.group(2).strip()

            # v9 FIX H: reject orphan WCAG cross-reference rows BEFORE adding to
            # `seen`, so the real 602.3 row (later in the document) is not blocked.
            # e.g. '602.3 (Support Docs)' appears in WCAG cells, not as a real entry.
            if re.search(
                r"\(Support Docs\)|\(Authoring Tool\)|\(Web\)|\(Software\)",
                m.group(2),
                re.IGNORECASE,
            ):
                continue

            if cid in seen:
                continue
            if _is_heading_row(row):
                continue
            seen.add(cid)

            found = find_row_status(row)

            criteria.append(
                VPATCriterion(
                    criterion_id=cid,
                    title=title,
                    level="",
                    raw_status=found.status,
                    normalized_status=normalize_status(found.status),
                    remarks=clean_remarks(found.remarks),
                    section="508_ch6",
                )
            )
    return criteria
