"""Reading a model's answer: find the JSON, then refuse to fix it.

Every rejection test here is guarding the same thing from a different angle. A
repaired answer is indistinguishable from a real one once it reaches the record,
and the record is what a reviewer acts on.
"""

from __future__ import annotations

import json

import pytest

from vpat_reviewer.ai import response
from vpat_reviewer.ai.base import NOT_ASSESSED, AssessmentError

_VALID = {
    "category": "Need TAAP",
    "confidence": 0.82,
    "risk_level": "High",
    "reason": "Keyboard access is Does Not Support at 2.1.1.",
    "regulatory_basis": {
        "ada_relevance": "Effective communication obligation.",
        "section_508_relevance": "E205 applies.",
        "wcag_relevance": "2.1.1 Keyboard, Level A.",
    },
    "signals_found": ["2.1.1 Does Not Support"],
    "major_accessibility_risks": ["Core workflows unreachable by keyboard"],
    "missing_or_unclear_information": ["No AT testing named"],
    "recommendation": "Request a remediation plan.",
    "next_steps": ["Escalate to a specialist"],
    "needs_human_review": True,
}


def _answer(**overrides) -> str:
    return json.dumps({**_VALID, **overrides})


def test_parses_a_bare_json_answer():
    verdict = response.parse(_answer(), model_id="test-model")
    assert verdict.category == "Need TAAP"
    assert verdict.risk_level == "High"
    assert verdict.confidence == 0.82
    assert verdict.model_id == "test-model"
    assert verdict.is_verdict
    assert verdict.signals_found == ("2.1.1 Does Not Support",)
    assert verdict.regulatory_basis.wcag_relevance == "2.1.1 Keyboard, Level A."


def test_parses_an_answer_in_a_code_fence():
    verdict = response.parse(f"```json\n{_answer()}\n```")
    assert verdict.category == "Need TAAP"


def test_parses_an_answer_wrapped_in_prose():
    """'Return strict JSON only' is a request, not a guarantee."""
    verdict = response.parse(f"Here is my assessment:\n\n{_answer()}\n\nHope this helps!")
    assert verdict.category == "Need TAAP"


def test_keeps_the_models_own_words():
    """Our reading of a model is lossy too, so the answer travels with the verdict."""
    text = _answer()
    assert response.parse(text).raw_response == text


def test_rejects_an_invented_category():
    with pytest.raises(AssessmentError, match="not one of the rubric's categories"):
        response.parse(_answer(category="Probably fine"))


def test_a_negated_verdict_is_not_the_verdict_it_negates():
    """The inversion regression, and the reason substring matching is banned.

    The previous implementation scanned aliases with ``if alias in value`` and
    tested "gtg" first, so a model answering "Not GTG" was recorded as **Good to
    Go** — inaccessible software filed as approved. Match the whole string.
    """
    for negated in ("Not GTG", "Not Good to Go", "not good", "definitely not Deny"):
        with pytest.raises(AssessmentError, match="not one of the rubric's categories"):
            response.parse(_answer(category=negated))


def test_json_without_a_category_is_not_a_verdict():
    """The invented-verdict regression.

    The previous implementation returned ``parsed_ok=True`` for any reply that
    contained *some* JSON, defaulting the missing category to "Needs Manual
    Review" — which the GUI then presented as the model's decision and filed the
    report on. A model that did not classify has not classified.
    """
    with pytest.raises(AssessmentError, match="no 'category'"):
        response.parse('{"reason": "The document is hard to read."}')


def test_a_casing_difference_is_the_same_category():
    """Case-insensitivity is not repair: one candidate, no guessing.

    Distinct from the "Not GTG" case above -- there, matching required
    *discarding* part of what the model said.
    """
    assert response.parse(_answer(category="good to go")).category == "Good to Go"
    assert response.parse(_answer(category="NEED TAAP")).category == "Need TAAP"
    assert response.parse(_answer(category="Minor issue")).category == "Minor Issue"


def test_rejects_the_not_assessed_sentinel():
    """'Not Assessed' is ours to say. A model must not be able to mint one."""
    with pytest.raises(AssessmentError, match="not a category an assessor may return"):
        response.parse(_answer(category=NOT_ASSESSED))


def test_rejects_a_missing_category():
    answer = {k: v for k, v in _VALID.items() if k != "category"}
    with pytest.raises(AssessmentError, match="no 'category'"):
        response.parse(json.dumps(answer))


def test_rejects_an_invented_risk_level():
    with pytest.raises(AssessmentError, match="not one of the rubric's risk levels"):
        response.parse(_answer(risk_level="Catastrophic"))


def test_rejects_out_of_range_confidence_rather_than_clamping_it():
    """Clamping 1.7 to 1.0 would invent a number the model never gave."""
    with pytest.raises(AssessmentError, match="between 0.0 and 1.0"):
        response.parse(_answer(confidence=1.7))
    with pytest.raises(AssessmentError, match="between 0.0 and 1.0"):
        response.parse(_answer(confidence=-0.5))


def test_rejects_non_numeric_confidence():
    with pytest.raises(AssessmentError, match="must be a number"):
        response.parse(_answer(confidence="high"))


def test_rejects_boolean_confidence():
    """bool is an int subclass: True would quietly become maximum confidence."""
    with pytest.raises(AssessmentError, match="must be a number"):
        response.parse(_answer(confidence=True))


def test_rejects_non_boolean_needs_human_review():
    with pytest.raises(AssessmentError, match="must be true or false"):
        response.parse(_answer(needs_human_review="yes"))


def test_rejects_a_non_list_where_a_list_belongs():
    with pytest.raises(AssessmentError, match="must be a list"):
        response.parse(_answer(signals_found="2.1.1 fails"))


def test_rejects_an_answer_that_is_not_json():
    with pytest.raises(AssessmentError, match="did not return a JSON object"):
        response.parse("I'm sorry, I can't help with that.")


def test_rejects_an_empty_answer():
    with pytest.raises(AssessmentError, match="did not return a JSON object"):
        response.parse("")


def test_ignores_keys_nobody_asked_for():
    """A volunteered field is not smuggled into the record under a name we never defined."""
    verdict = response.parse(_answer(severity_score=11, internal_notes="ignore me"))
    assert not hasattr(verdict, "severity_score")
    assert "severity_score" not in verdict.to_dict()


def test_absent_optional_fields_default_rather_than_fail():
    """Only category is truly required; the rest degrade to empty, not to a guess."""
    verdict = response.parse(json.dumps({"category": "Good to Go", "confidence": 0.5}))
    assert verdict.category == "Good to Go"
    assert verdict.risk_level == "Unknown"
    assert verdict.signals_found == ()
    assert verdict.regulatory_basis.ada_relevance == ""
    assert verdict.needs_human_review is True
