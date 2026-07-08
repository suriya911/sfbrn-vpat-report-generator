"""Domain data models.

These are relocated verbatim (with explicit typing) from the v10 parser. They
remain *mutable* on purpose: the parser builds a document incrementally
(constructs, then appends criteria and sets metadata). A later phase may
introduce a build-then-freeze immutable variant; changing mutability now would
break the strangler contract of "the app keeps working at every step".

``VPATData`` is kept as an alias of ``VPATDocument`` so legacy modules and the
compatibility shim in ``vpat_parser`` continue to import the old name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class VPATCriterion:
    """A single WCAG / Section 508 criterion row parsed from a vendor VPAT."""

    criterion_id: str = ""
    title: str = ""
    level: str = ""
    raw_status: str = ""
    normalized_status: str = "Not Evaluated"
    remarks: str = ""
    section: str = "wcag"


@dataclass
class VPATDocument:
    """Everything parsed from a vendor VPAT document."""

    product_name: str = ""
    product_version: str = ""
    vendor_name: str = ""
    vendor_report_date_raw: str = ""
    vendor_report_date: date | None = None
    vpat_edition: str = ""
    vendor_contact: str = ""
    sfbrn_contact: str = ""
    product_description: str = ""
    product_type: str = "Software"
    evaluation_methods: str = ""
    standards_reviewed: list[str] = field(default_factory=list)
    criteria: list[VPATCriterion] = field(default_factory=list)
    raw_text: str = ""
    parse_warnings: list[str] = field(default_factory=list)
    is_outdated: bool = False
    outdated_note: str = ""


# Backward-compatible alias for the legacy name used across the v10 codebase.
VPATData = VPATDocument
