"""Edge-case coverage for the response validator (``ai/response.py``).

The teammate's ``test_response`` covers the headline reject-never-repair rules
(bad category, out-of-range confidence). These fill the remaining branches: the
list- and object-shaped fields must be the right *shape* or the whole reply is
rejected — a string where a list belongs is a malformed answer, not something to
coerce.
"""

import json

import pytest

from vpat_reviewer.ai.base import AssessmentError
from vpat_reviewer.ai.response import parse


def _reply(**overrides) -> str:
    base = {
        "category": "Deny",
        "risk_level": "High",
        "confidence": 0.5,
        "needs_human_review": True,
    }
    base.update(overrides)
    return json.dumps(base)


def test_a_list_field_given_as_a_string_is_rejected():
    with pytest.raises(AssessmentError, match="must be a list"):
        parse(_reply(signals_found="just one string"))


def test_regulatory_basis_given_as_a_string_is_rejected():
    with pytest.raises(AssessmentError, match="must be an object"):
        parse(_reply(regulatory_basis="ADA and 508"))


def test_list_fields_are_read_when_well_formed():
    a = parse(
        _reply(
            signals_found=["signal one", "signal two"],
            major_accessibility_risks=["a risk"],
            missing_or_unclear_information=["a gap"],
            next_steps=["step one"],
        )
    )
    assert a.signals_found == ("signal one", "signal two")
    assert a.major_accessibility_risks == ("a risk",)
    assert a.missing_or_unclear_information == ("a gap",)
    assert a.next_steps == ("step one",)


def test_regulatory_basis_object_is_read_field_by_field():
    a = parse(
        _reply(
            regulatory_basis={
                "ada_relevance": "ada text",
                "section_508_relevance": "508 text",
                "wcag_relevance": "wcag text",
            }
        )
    )
    assert a.regulatory_basis.ada_relevance == "ada text"
    assert a.regulatory_basis.section_508_relevance == "508 text"
    assert a.regulatory_basis.wcag_relevance == "wcag text"


def test_absent_optional_fields_default_empty():
    a = parse(_reply())
    assert a.signals_found == ()
    assert a.regulatory_basis.ada_relevance == ""


def test_explicit_null_optional_fields_default_empty():
    # A model may send `null` rather than omit the key — that is empty, not an
    # error (distinct from the absent case, which never reaches the null branch).
    a = parse(_reply(signals_found=None, regulatory_basis=None))
    assert a.signals_found == ()
    assert a.regulatory_basis.ada_relevance == ""
