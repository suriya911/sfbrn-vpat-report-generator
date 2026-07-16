"""Status normalization — maps the many ways vendors phrase a conformance
status onto the five canonical statuses used throughout the app.

Relocated verbatim from the v10 parser; behavior is unchanged. The map is data,
so new vendor phrasings are added here (or, later, via settings) rather than by
editing branching logic.
"""

from __future__ import annotations

# Canonical statuses the rest of the system reasons about.
SUPPORTS = "Supports"
PARTIALLY_SUPPORTS = "Partially Supports"
DOES_NOT_SUPPORT = "Does Not Support"
NOT_APPLICABLE = "Not Applicable"
NOT_EVALUATED = "Not Evaluated"

CANONICAL_STATUSES = (
    SUPPORTS,
    PARTIALLY_SUPPORTS,
    DOES_NOT_SUPPORT,
    NOT_APPLICABLE,
    NOT_EVALUATED,
)

_STATUS_MAP: dict[str, str] = {
    "supports": "Supports",
    "supported": "Supports",
    "fully supports": "Supports",
    "full support": "Supports",
    "support": "Supports",  # common vendor typo
    "partially supports": "Partially Supports",
    "partially supported": "Partially Supports",
    "partial supports": "Partially Supports",
    "partially support": "Partially Supports",
    "supports with exceptions": "Partially Supports",
    "support with exceptions": "Partially Supports",
    "does not support": "Does Not Support",
    "does not supports": "Does Not Support",
    "not supported": "Does Not Support",
    "unsupported": "Does Not Support",
    "not support": "Does Not Support",
    "not applicable": "Not Applicable",
    "n/a": "Not Applicable",
    "na": "Not Applicable",
    # Seen on a real ACR against 4.1.1 Parsing, which WCAG 2.2 removed. Note it
    # must not be read as a "does not ..." negative: the vendor means the
    # criterion does not apply, not that the product fails it.
    "does not apply": "Not Applicable",
    "not evaluated": "Not Evaluated",
    # Vendor typo / alternate phrasing variants
    "partial support": "Partially Supports",  # missing trailing 's'
    "partial supported": "Partially Supports",
    "limited support": "Partially Supports",  # sometimes used by vendors
    "mostly supports": "Partially Supports",
    "supports except": "Partially Supports",
    "not meet": "Does Not Support",
    "does not meet": "Does Not Support",
    "not comply": "Does Not Support",
    # Non-standard values from specific VPAT tools
    "see wcag 2.1 section": "Not Evaluated",
    "heading cell": "Not Evaluated",
    "heading cell – no response required": "Not Evaluated",
}


def normalize_status(raw: str) -> str:
    """Normalize a raw vendor status string to one of ``CANONICAL_STATUSES``.

    The ordering of the fuzzy checks matters: ``partial`` is tested before the
    generic ``support`` check so "Partial Support" never collapses to
    "Supports". This is a regression-protected behavior (v9 FIX F).
    """
    if not raw:
        return "Not Evaluated"
    c = raw.strip().lower()
    if c in _STATUS_MAP:
        return _STATUS_MAP[c]
    for key, val in _STATUS_MAP.items():
        if c.startswith(key):
            return val
    if "does not support" in c or "not supported" in c or "unsupported" in c:
        return "Does Not Support"
    # "partial" must be checked BEFORE the generic "support" check to prevent
    # "partial support" -> "Supports".
    if "partially" in c or "partial" in c or "exceptions" in c:
        return "Partially Supports"
    if "not applicable" in c or c == "n/a":
        return "Not Applicable"
    if "not evaluated" in c:
        return "Not Evaluated"
    # Generic "support" check — only reached if no other match. Guard: must not
    # contain "not" (handled above) or "partial".
    if "support" in c and "partial" not in c and "not" not in c:
        return "Supports"
    return "Not Evaluated"
