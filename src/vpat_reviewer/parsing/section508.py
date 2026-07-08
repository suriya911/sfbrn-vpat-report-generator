"""Section 508 parsing: functional performance criteria (302.x) and Chapter 6
(602/603.x). Relocated verbatim from the v10 parser.
"""

from __future__ import annotations

import re

from vpat_reviewer.domain.models import VPATCriterion
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.extraction.base import Table
from vpat_reviewer.parsing.criteria import clean_remarks

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
            seen.add(cid)
            title = FPC_TITLES.get(cid, m.group(2).strip())

            if len(row) >= 9:
                raw_status, remarks = str(row[3] or "").strip(), str(row[6] or "").strip()
            elif len(row) >= 3:
                raw_status, remarks = str(row[1] or "").strip(), str(row[2] or "").strip()
            elif len(row) >= 2:
                raw_status, remarks = str(row[1] or "").strip(), ""
            else:
                raw_status, remarks = "", ""

            if "heading cell" in raw_status.lower():
                continue

            criteria.append(
                VPATCriterion(
                    criterion_id=cid,
                    title=title,
                    level="",
                    raw_status=raw_status,
                    normalized_status=normalize_status(raw_status),
                    remarks=clean_remarks(remarks),
                    section="508_fpc",
                )
            )

    # Text fallback — build all 9 criteria if none found from tables.
    if not criteria:
        for cid, ctitle in FPC_TITLES.items():
            if cid in seen:
                continue
            seen.add(cid)
            pat = re.compile(
                re.escape(cid) + r".{0,200}?"
                r"(Supports\s+with\s+Exceptions|Partially\s+Supports?|Does\s+Not\s+Supports?|"
                r"Not\s+Applicable|Not\s+Evaluated|Supports?)",
                re.IGNORECASE | re.DOTALL,
            )
            m2 = pat.search(text)
            raw_status = m2.group(1) if m2 else ""
            remarks_text = ""
            if m2:
                chunk = text[m2.end() : m2.end() + 500]
                stop = re.search(r"302\.\d|Chapter\s+[456]", chunk)
                remarks_text = chunk[: stop.start() if stop else 300]
                remarks_text = re.sub(r"\s+", " ", remarks_text).strip()
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
            seen.add(cid)

            if len(row) >= 9:
                raw_status, remarks = str(row[3] or "").strip(), str(row[6] or "").strip()
            elif len(row) >= 3:
                raw_status, remarks = str(row[1] or "").strip(), str(row[2] or "").strip()
            else:
                raw_status = str(row[1] or "").strip() if len(row) > 1 else ""
                remarks = ""

            if "heading cell" in raw_status.lower():
                continue
            normed = normalize_status(raw_status)

            criteria.append(
                VPATCriterion(
                    criterion_id=cid,
                    title=title,
                    level="",
                    raw_status=raw_status,
                    normalized_status=normed,
                    remarks=clean_remarks(remarks),
                    section="508_ch6",
                )
            )
    return criteria
