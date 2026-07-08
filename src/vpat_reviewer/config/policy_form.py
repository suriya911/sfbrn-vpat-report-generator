"""UI-agnostic editing of the grading policy.

The CLI and the GUI both edit the policy through this module, so the rules for
"what is editable and how a value is validated" live in exactly one place (and
are unit-tested). Values come in as strings (from a form field or the command
line); each setter returns ``(new_policy, error)`` — ``error`` is ``None`` on
success, otherwise a human-readable message and the policy is unchanged.
"""

from __future__ import annotations

from typing import Any

from vpat_reviewer.domain.normalization import CANONICAL_STATUSES
from vpat_reviewer.domain.policy import GradingPolicy, ScoreBand

# Simple scalar/list knobs a friendly form exposes. Score bands are edited
# separately via ``set_band`` because each band has three sub-fields.
EDITABLE_FIELDS: list[dict[str, Any]] = [
    {"key": "graded_level", "label": "WCAG level graded", "type": "choice", "choices": ["A", "AA"]},
    {"key": "compliance_threshold", "label": "Compliance threshold (%)", "type": "int"},
    {
        "key": "supported_statuses",
        "label": "Statuses that count as a pass",
        "type": "status_list",
        "choices": list(CANONICAL_STATUSES),
    },
    {
        "key": "excluded_statuses",
        "label": "Statuses excluded from the denominator",
        "type": "status_list",
        "choices": list(CANONICAL_STATUSES),
    },
]

_LIST_KEYS = {"supported_statuses", "excluded_statuses"}
_STR_KEYS = {"graded_level", "core_block_status"}


def current_values(policy: GradingPolicy) -> dict[str, Any]:
    """A plain-dict view of the editable fields, for populating a form."""
    return {
        "graded_level": policy.graded_level,
        "compliance_threshold": policy.compliance_threshold,
        "supported_statuses": list(policy.supported_statuses),
        "excluded_statuses": list(policy.excluded_statuses),
        "core_block_status": policy.core_block_status,
        "score_bands": [
            {"min_score": b.min_score, "label": b.label, "message": b.message}
            for b in policy.score_bands
        ],
    }


def _as_status_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        parts = [s.strip() for s in value.split(",")]
    else:
        parts = [str(s).strip() for s in value]
    return tuple(p for p in parts if p)


def set_field(policy: GradingPolicy, key: str, value: Any) -> tuple[GradingPolicy, str | None]:
    """Set one scalar/list field. Returns ``(policy, error)``."""
    if key in _LIST_KEYS:
        statuses = _as_status_tuple(value)
        if not statuses and key == "supported_statuses":
            return policy, "supported_statuses must list at least one status."
        unknown = [s for s in statuses if s not in CANONICAL_STATUSES]
        if unknown:
            return policy, f"unknown status(es): {', '.join(unknown)}"
        candidate = policy.with_changes(**{key: statuses})
    elif key == "compliance_threshold":
        try:
            iv = int(value)
        except (TypeError, ValueError):
            return policy, "compliance_threshold must be a whole number."
        candidate = policy.with_changes(compliance_threshold=iv)
    elif key in _STR_KEYS:
        text = str(value).strip()
        if not text:
            return policy, f"{key} must not be empty."
        candidate = policy.with_changes(**{key: text})
    else:
        return policy, f"unknown field '{key}'."

    problems = candidate.validate()
    if problems:
        return policy, "; ".join(problems)
    return candidate, None


def from_form(
    base: GradingPolicy, values: dict[str, Any]
) -> tuple[GradingPolicy | None, list[str]]:
    """Rebuild a policy from a full set of form values (used by the GUI dialog).

    ``values`` keys: ``graded_level``, ``compliance_threshold`` (str/int),
    ``supported_statuses`` / ``excluded_statuses`` (lists), and ``bands`` (a list
    of ``{"min_score", "label", "message"}``). Returns ``(policy, [])`` on
    success or ``(None, errors)`` if anything is invalid.
    """
    errors: list[str] = []
    data = base.to_dict()
    data["graded_level"] = str(values.get("graded_level", base.graded_level)).strip()

    try:
        data["compliance_threshold"] = int(values["compliance_threshold"])
    except (KeyError, TypeError, ValueError):
        errors.append("Compliance threshold must be a whole number.")

    data["supported_statuses"] = list(values.get("supported_statuses", base.supported_statuses))
    data["excluded_statuses"] = list(values.get("excluded_statuses", base.excluded_statuses))

    bands = []
    for b in values.get("bands", data["score_bands"]):
        try:
            mn = int(b["min_score"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"Band '{b.get('label', '?')}' minimum score must be a whole number.")
            continue
        bands.append({"min_score": mn, "label": str(b["label"]), "message": str(b["message"])})
    data["score_bands"] = bands

    unknown = [s for s in data["supported_statuses"] if s not in CANONICAL_STATUSES]
    if unknown:
        errors.append(f"Unknown supported status(es): {', '.join(unknown)}")

    if errors:
        return None, errors

    policy = GradingPolicy.from_dict(data)
    problems = policy.validate()
    if problems:
        return None, problems
    return policy, []


def set_band(
    policy: GradingPolicy, index: int, subfield: str, value: Any
) -> tuple[GradingPolicy, str | None]:
    """Edit one score band's ``min_score`` / ``label`` / ``message``."""
    bands = list(policy.score_bands)
    if not 0 <= index < len(bands):
        return policy, f"band index {index} out of range (0..{len(bands) - 1})."
    band = bands[index]
    if subfield == "min_score":
        try:
            iv = int(value)
        except (TypeError, ValueError):
            return policy, "min_score must be a whole number."
        band = ScoreBand(iv, band.label, band.message)
    elif subfield == "label":
        band = ScoreBand(band.min_score, str(value), band.message)
    elif subfield == "message":
        band = ScoreBand(band.min_score, band.label, str(value))
    else:
        return policy, f"unknown band field '{subfield}'."
    bands[index] = band
    candidate = policy.with_changes(score_bands=tuple(bands))
    problems = candidate.validate()
    if problems:
        return policy, "; ".join(problems)
    return candidate, None
