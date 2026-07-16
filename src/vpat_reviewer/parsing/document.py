"""Assemble a ``VPATDocument`` from a :class:`RawDocument`, and the file entry point.

``parse_document`` is pure (text + tables in, document out) and is the seam the
fixture corpus tests against. ``parse_vpat`` is the thin file-facing wrapper:
extract -> parse.
"""

from __future__ import annotations

import logging
from datetime import date

from vpat_reviewer.domain.models import DocumentKind, VPATCriterion, VPATDocument
from vpat_reviewer.extraction import RawDocument, UnsupportedFormatError, extract
from vpat_reviewer.parsing.criteria import parse_from_tables, parse_from_text
from vpat_reviewer.parsing.dates import parse_date
from vpat_reviewer.parsing.doctype import classify_document
from vpat_reviewer.parsing.metadata import extract_meta
from vpat_reviewer.parsing.section508 import parse_508_ch6, parse_508_fpc
from vpat_reviewer.parsing.standards import detect_standards

logger = logging.getLogger(__name__)


def _parse_criteria(raw: RawDocument) -> list[VPATCriterion]:
    """Criteria from the tables, with prose used to fill in what they lack.

    Tables are authoritative: a cell's position ties an answer to its criterion,
    which flowed text cannot. But a table row we located and could not read is
    precisely where the prose is worth consulting -- so the text parser is held
    off only for criteria that already have an answer, and anything it recovers
    is merged into the existing row rather than appended beside it.
    """
    table_criteria = parse_from_tables(raw.tables)
    answered = {c.criterion_id for c in table_criteria if c.raw_status.strip()}
    text_criteria = parse_from_text(raw.text, set(answered))

    by_id = {c.criterion_id: c for c in table_criteria}
    merged = list(table_criteria)
    for found in text_criteria:
        existing = by_id.get(found.criterion_id)
        if existing is None:
            merged.append(found)
            by_id[found.criterion_id] = found
        elif found.raw_status.strip():
            existing.raw_status = found.raw_status
            existing.normalized_status = found.normalized_status
            existing.remarks = existing.remarks or found.remarks
    return merged


def parse_document(raw: RawDocument) -> VPATDocument:
    """Turn extracted text + tables into a populated ``VPATDocument``."""
    data = VPATDocument()
    data.raw_text = raw.text

    meta = extract_meta(raw.text)
    data.product_name = meta.get("product_name", "")
    data.product_version = meta.get("product_version", "")
    data.vendor_name = meta.get("vendor_name", "")
    data.vendor_report_date_raw = meta.get("vendor_report_date_raw", "")
    data.vpat_edition = meta.get("vpat_edition", "")
    data.vendor_contact = meta.get("vendor_contact", "")
    data.product_description = meta.get("product_description", "")
    data.product_type = meta.get("product_type", "Software")
    data.evaluation_methods = meta.get("evaluation_methods", "")

    parsed_dt = parse_date(data.vendor_report_date_raw)
    if parsed_dt:
        data.vendor_report_date = parsed_dt
        delta = (date.today() - parsed_dt).days
        if delta > 365:
            data.is_outdated = True
            months = delta // 30
            data.outdated_note = (
                f"The vendor report date ({data.vendor_report_date_raw}) is approximately "
                f"{months} months old. VPATs older than 12 months may not reflect the current "
                f"accessibility state of the product. SFBRN recommends requesting an updated "
                f"VPAT before final procurement decisions."
            )

    data.standards_reviewed = detect_standards(raw.text) or []

    data.criteria = _parse_criteria(raw)

    data.criteria += parse_508_fpc(raw.tables, raw.text)
    data.criteria += parse_508_ch6(raw.tables)

    verdict = classify_document(raw.text, data.criteria)
    data.document_kind = verdict.kind
    data.document_kind_reasons = list(verdict.reasons)
    if verdict.kind is not DocumentKind.VPAT:
        data.parse_warnings.append(
            f"This does not look like a completed VPAT ({verdict.kind.value}): "
            + "; ".join(verdict.reasons)
        )

    logger.info(
        "Parsed: product='%s' vendor='%s' criteria=%d kind=%s outdated=%s",
        data.product_name,
        data.vendor_name,
        len(data.criteria),
        data.document_kind.value,
        data.is_outdated,
    )
    return data


def parse_vpat(filepath: str) -> VPATDocument:
    """Extract and parse a VPAT file (PDF/DOCX/TXT) into a ``VPATDocument``."""
    data = VPATDocument()
    try:
        raw = extract(filepath)
    except UnsupportedFormatError as e:
        data.parse_warnings.append(str(e))
        return data
    if raw.is_empty:
        data.parse_warnings.append("No text could be extracted.")
        return data
    return parse_document(raw)
