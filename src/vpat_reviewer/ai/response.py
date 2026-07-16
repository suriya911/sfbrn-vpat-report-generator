"""Reading an assessor's answer back into a verdict.

The rubric asks for strict JSON. Models answer with strict JSON wrapped in a code
fence, or prefaced with "Here's my assessment:", or with a category they invented.
This module finds the JSON and checks it against the rubric's schema.

The rule throughout is **reject, never repair**. A confidence of 1.7 is not
clamped to 1.0, and a category of "Probably fine" is not mapped to the nearest
real one: both would replace what the assessor said with something we made up,
and the record would then state our invention as the model's judgment. Anything
that fails to validate raises, and the caller records an honest non-verdict.
"""

from __future__ import annotations

import json
import re
from typing import Any

from vpat_reviewer.ai.base import (
    CATEGORIES,
    NOT_ASSESSED,
    RISK_LEVELS,
    AssessmentError,
    RegulatoryBasis,
    RiskAssessment,
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _find_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a model's answer, however it wrapped it."""
    candidates = [text.strip()]

    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data

    raise AssessmentError("The assessor did not return a JSON object.")


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key, "")
    return "" if value is None else str(value)


def _strings(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if value in (None, ""):
        return ()
    if not isinstance(value, list):
        raise AssessmentError(f"{key!r} must be a list, got {type(value).__name__}.")
    return tuple(str(v) for v in value)


def _canonical_category(category: str) -> str:
    """The rubric's exact spelling of ``category``, or raise.

    Matching is case-insensitive and nothing more. That is not repair: there is
    exactly one candidate for "good to go" and no judgment involved in picking
    it. Substring matching *would* be repair, and was a real bug — the previous
    implementation scanned aliases with ``if alias in value``, so a model
    answering "Not GTG" matched the "gtg" alias and was recorded as **Good to
    Go**. Inaccessible software, filed as approved. Match the whole string or
    reject it.
    """
    if not category:
        raise AssessmentError("The assessor returned no 'category'.")
    folded = category.casefold()
    if folded == NOT_ASSESSED.casefold():
        # Ours to say, not the model's. If it could return the sentinel it could
        # opt out of the rubric while looking like our own honest non-verdict.
        raise AssessmentError(f"{NOT_ASSESSED!r} is not a category an assessor may return.")
    for canonical in CATEGORIES:
        if folded == canonical.casefold():
            return canonical
    raise AssessmentError(f"{category!r} is not one of the rubric's categories: {CATEGORIES}.")


def _confidence(data: dict[str, Any]) -> float:
    value = data.get("confidence", 0.0)
    # bool is an int subclass, and True would silently become 1.0 -- a maximally
    # confident verdict conjured from a type error.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssessmentError(f"'confidence' must be a number, got {value!r}.")
    if not 0.0 <= float(value) <= 1.0:
        # Not clamped: 1.7 means the assessor was not answering the question we
        # asked, and pretending it said 1.0 invents a number it never gave.
        raise AssessmentError(f"'confidence' must be between 0.0 and 1.0, got {value!r}.")
    return float(value)


def _regulatory_basis(data: dict[str, Any]) -> RegulatoryBasis:
    value = data.get("regulatory_basis", {})
    if value in (None, ""):
        return RegulatoryBasis()
    if not isinstance(value, dict):
        raise AssessmentError(f"'regulatory_basis' must be an object, got {type(value).__name__}.")
    return RegulatoryBasis(
        ada_relevance=_text(value, "ada_relevance"),
        section_508_relevance=_text(value, "section_508_relevance"),
        wcag_relevance=_text(value, "wcag_relevance"),
    )


def parse(text: str, *, model_id: str = "") -> RiskAssessment:
    """Read an assessor's answer as a verdict, or raise :class:`AssessmentError`.

    Keys we did not ask for are ignored rather than absorbed: the record carries
    exactly the fields the rubric promises, and anything else a model volunteers
    is not smuggled into it under a name nobody defined.
    """
    data = _find_json(text)

    category = _canonical_category(_text(data, "category").strip())

    risk_level = _text(data, "risk_level").strip() or "Unknown"
    if risk_level not in RISK_LEVELS:
        raise AssessmentError(f"{risk_level!r} is not one of the rubric's risk levels.")

    needs_human_review = data.get("needs_human_review", True)
    if not isinstance(needs_human_review, bool):
        raise AssessmentError(
            f"'needs_human_review' must be true or false, got {needs_human_review!r}."
        )

    return RiskAssessment(
        category=category,
        risk_level=risk_level,
        confidence=_confidence(data),
        reason=_text(data, "reason"),
        regulatory_basis=_regulatory_basis(data),
        signals_found=_strings(data, "signals_found"),
        major_accessibility_risks=_strings(data, "major_accessibility_risks"),
        missing_or_unclear_information=_strings(data, "missing_or_unclear_information"),
        recommendation=_text(data, "recommendation"),
        next_steps=_strings(data, "next_steps"),
        needs_human_review=needs_human_review,
        model_id=model_id,
        raw_response=text,
    )
