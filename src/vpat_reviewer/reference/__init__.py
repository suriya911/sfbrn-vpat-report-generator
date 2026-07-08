"""WCAG reference data (titles, descriptions, plain language, workarounds).

Data lives in ``data/wcag.json``; edit that file to change what the report
quotes. Access it through this package's functions.
"""

from vpat_reviewer.reference.loader import (
    REQUIRED_IDS,
    all_criteria,
    has_all_required,
    lookup,
    title,
    workarounds,
)

__all__ = [
    "REQUIRED_IDS",
    "all_criteria",
    "has_all_required",
    "lookup",
    "title",
    "workarounds",
]
