"""Status normalization — maps the many ways vendors phrase a conformance
status onto the five canonical statuses used throughout the app.

The map is data, so new vendor phrasings are added here (or, later, via
settings) rather than by editing branching logic.

Some vendors (Google's ACRs) answer a criterion once per reporting target:
"Web: Partially Supports" and "Authoring Tool: Supports" in the same cell.
``split_components`` recognizes that shape, and ``normalize_status`` folds it
to a single canonical status by worst-wins (see ``_SEVERITY``).
"""

from __future__ import annotations

import re

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


# The reporting targets the ITI VPAT template answers per criterion. This is a
# deliberately CLOSED list: segmentation only ever fires on these names, so a
# remarks sentence that happens to contain a colon ("Clarification: ...") can
# never be read as a conformance value. Multi-word names come first so the
# alternation prefers "Support Docs" over a shorter accidental match.
_COMPONENT_NAMES = (
    "Authoring Tool",
    "Electronic Docs",
    "Support Docs",
    "Product Docs",
    "Documentation",
    "Docs",
    "Web",
    "Software",
    "Hardware",
    "Open",
    "Closed",
    "Both",
)

# One component prefix, e.g. "Web:", "Authoring Tool:", "Web (partial):".
COMPONENT_PREFIX_PATTERN = (
    r"(?:" + "|".join(name.replace(" ", r"\s*") for name in _COMPONENT_NAMES) + r")"
    r"(?:\s*\([^)]*\))?\s*:\s*"
)
_COMPONENT_SPLIT_RE = re.compile(r"\b" + COMPONENT_PREFIX_PATTERN, re.IGNORECASE)

# Worst-wins severity, ascending. Not Evaluated outranks Supports: a component
# whose conformance is unknown means the row cannot honestly claim "Supports".
# Not Applicable ranks lowest: it is excluded from grading because the feature
# is absent, a rationale that stops applying the moment another component
# answers -- so a mixed NA row takes the answering component's status.
_SEVERITY = (
    NOT_APPLICABLE,
    SUPPORTS,
    NOT_EVALUATED,
    PARTIALLY_SUPPORTS,
    DOES_NOT_SUPPORT,
)


def split_components(raw: str) -> list[str] | None:
    """Split a multi-component status into its per-component answers.

    "Web: Partially Supports Authoring Tool: Supports" ->
    ["Partially Supports", "Supports"]. Returns ``None`` unless the string
    *starts* with a known component prefix and contains at least two of them —
    single-prefix values ("Web: Supports") keep their existing handling.
    """
    text = raw.strip()
    marks = list(_COMPONENT_SPLIT_RE.finditer(text))
    if len(marks) < 2 or marks[0].start() != 0:
        return None
    ends = [m.start() for m in marks[1:]] + [len(text)]
    return [text[m.end() : end].strip() for m, end in zip(marks, ends, strict=True)]


def normalize_status(raw: str) -> str:
    """Normalize a raw vendor status string to one of ``CANONICAL_STATUSES``.

    The ordering of the fuzzy checks matters: ``partial`` is tested before the
    generic ``support`` check so "Partial Support" never collapses to
    "Supports". This is a regression-protected behavior (v9 FIX F).
    """
    if not raw:
        return "Not Evaluated"

    # Multi-component answers fold to worst-wins -- but only when every
    # segment is a status we recognize exactly. One unreadable segment sends
    # the whole string to the fuzzy path below, which can never do worse than
    # "Not Evaluated".
    segments = split_components(raw)
    if segments is not None:
        statuses: list[str] = []
        for segment in segments:
            hit = _STATUS_MAP.get(segment.strip().lower())
            if hit is None:
                statuses = []
                break
            statuses.append(hit)
        if statuses:
            return max(statuses, key=_SEVERITY.index)

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
