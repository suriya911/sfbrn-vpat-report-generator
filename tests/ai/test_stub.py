"""The stub satisfies the port and refuses to judge.

The refusal is the interesting part: a stub that returned a plausible category
would be indistinguishable from a real verdict everywhere downstream, and would
survive all the way onto a reviewer's desk.
"""

from __future__ import annotations

import pytest

from vpat_reviewer.ai.base import (
    CATEGORIES,
    NOT_ASSESSED,
    AssessmentError,
    AssessmentRequest,
    RiskAssessor,
)
from vpat_reviewer.ai.stub import StubAssessor


def _request(prompt: str = "Classify this VPAT.") -> AssessmentRequest:
    return AssessmentRequest(prompt=prompt, record={"document_kind": "vpat"})


def test_stub_satisfies_the_port():
    assert isinstance(StubAssessor(), RiskAssessor)


def test_stub_never_returns_a_rubric_category():
    """The load-bearing assertion: a stub must not be able to look like a verdict."""
    verdict = StubAssessor().assess(_request())
    assert verdict.category == NOT_ASSESSED
    assert verdict.category not in CATEGORIES
    assert not verdict.is_verdict


def test_stub_claims_no_confidence_and_asks_for_a_human():
    verdict = StubAssessor().assess(_request())
    assert verdict.confidence == 0.0
    assert verdict.risk_level == "Unknown"
    assert verdict.needs_human_review is True
    assert verdict.model_id == "stub"


def test_stub_explains_itself():
    """The record has to say *why* there's no verdict, or it reads as a failure."""
    verdict = StubAssessor().assess(_request())
    assert "stub" in verdict.reason.lower()
    assert verdict.error == ""


def test_stub_is_deterministic():
    assessor = StubAssessor()
    assert assessor.assess(_request()) == assessor.assess(_request())


def test_stub_rejects_an_empty_prompt():
    """A render() regression must surface here, not produce a well-formed nothing."""
    with pytest.raises(AssessmentError, match="empty"):
        StubAssessor().assess(_request(prompt="   "))
