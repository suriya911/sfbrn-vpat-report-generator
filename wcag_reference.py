"""wcag_reference — compatibility shim (Phase 4 strangler).

The WCAG reference dataset now lives in ``vpat_reviewer/reference/data/wcag.json``
and is served by ``vpat_reviewer.reference.loader``. This module preserves the
v10 API (``lookup``, ``has_all_required``, ``WCAG_REFERENCE``) so the legacy
``report_generator`` keeps working unchanged.
"""

from vpat_reviewer.reference.loader import all_criteria, has_all_required, lookup

# Legacy module-level dataset (kept for any code that read it directly).
WCAG_REFERENCE = all_criteria()

__all__ = ["WCAG_REFERENCE", "lookup", "has_all_required"]


if __name__ == "__main__":
    ok, missing = has_all_required()
    print(f"WCAG reference entries: {len(WCAG_REFERENCE)}")
    print(f"Required present: {ok}" + ("" if ok else f" — missing {missing}"))
