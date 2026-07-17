"""The assessment stage: injectable, and unable to lose a review.

This is the seam the model plugs into. Two things it must never do: reach for a
network on its own, and turn a bad model reply into either a crash or a verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

from vpat_reviewer import service
from vpat_reviewer.ai.base import (
    CATEGORIES,
    NOT_ASSESSED,
    AssessmentError,
    AssessmentRequest,
    RiskAssessment,
)
from vpat_reviewer.ai.stub import StubAssessor
from vpat_reviewer.domain.policy import GradingPolicy

FIXTURE = Path(__file__).parent / "fixtures" / "txt" / "acme_basic.txt"


class _FixedAssessor:
    """Answers with one verdict, and remembers what it was asked."""

    model_id = "test.model.v1"

    def __init__(self, category: str = "Need TAAP"):
        self._category = category
        self.request: AssessmentRequest | None = None

    def assess(self, request: AssessmentRequest) -> RiskAssessment:
        self.request = request
        return RiskAssessment(
            category=self._category,
            risk_level="High",
            confidence=0.9,
            reason="Test verdict.",
            model_id=self.model_id,
        )


class _FailingAssessor:
    model_id = "test.model.v1"

    def assess(self, request: AssessmentRequest) -> RiskAssessment:
        raise AssessmentError("the model returned prose")


def _analyzed() -> service.ReviewResult:
    return service.analyze(str(FIXTURE), policy=GradingPolicy.default())


def test_analysis_has_not_run_until_it_is_asked_for():
    """Absent, not guessed: no assessment means no assessment field."""
    result = _analyzed()
    assert result.assessment is None
    assert service.to_dict(result)["assessment"] is None


def test_assessment_lands_in_the_record():
    result = service.assess_result(_analyzed(), assessor=_FixedAssessor())
    block = service.to_dict(result)["assessment"]
    assert block["category"] == "Need TAAP"
    assert block["risk_level"] == "High"
    assert block["confidence"] == 0.9
    assert block["model_id"] == "test.model.v1"


def test_record_with_an_assessment_is_still_json_serializable():
    result = service.assess_result(_analyzed(), assessor=_FixedAssessor())
    json.dumps(service.to_dict(result))


def test_a_failing_assessor_costs_the_verdict_not_the_review():
    result = service.assess_result(_analyzed(), assessor=_FailingAssessor())
    assert result.assessment is not None
    assert result.assessment.category == NOT_ASSESSED
    assert result.assessment.category not in CATEGORIES
    assert "prose" in result.assessment.error
    # The analysis itself survives intact.
    assert service.to_dict(result)["score"] == 50


def test_the_assessor_is_shown_the_document_not_our_verdict():
    """Anchoring guard: a re-run must not feed the model its own previous answer.

    The rubric names every category, so the check has to be against the record
    payload -- "Deny" appears in any prompt by construction.
    """
    result = _analyzed()
    service.assess_result(result, assessor=_FixedAssessor(category="Deny"))

    second = _FixedAssessor()
    service.assess_result(result, assessor=second)

    assert second.request is not None
    assert "assessment" not in second.request.record
    payload = second.request.prompt.split("VPAT/ACR content:\n", 1)[1]
    assert "assessment" not in json.loads(payload)
    assert "Deny" not in payload


def test_the_assessor_is_shown_the_parsed_evidence():
    assessor = _FixedAssessor()
    service.assess_result(_analyzed(), assessor=assessor)

    assert assessor.request is not None
    record = assessor.request.record
    assert record["document_kind"] == "vpat"
    assert record["product_name"] == "Acme Learn"
    by_id = {c["id"]: c for c in record["criteria"]}
    assert by_id["1.4.3"]["raw_status"] == "Partially Supports"
    assert "Acme Learn" in assessor.request.prompt


def test_a_prebuilt_request_is_not_rebuilt():
    """The caller logs what it sent, so it must be what was asked."""
    request = service.build_assessment_request(_analyzed())
    assessor = _FixedAssessor()
    service.assess_result(_analyzed(), assessor=assessor, request=request)
    assert assessor.request is request


def test_the_stub_produces_no_verdict():
    result = service.assess_result(_analyzed(), assessor=StubAssessor())
    assert result.assessment is not None
    assert result.assessment.model_id == "stub"
    assert result.assessment.category == NOT_ASSESSED


def test_review_does_not_assess(tmp_path: Path):
    """The offline pipeline stays offline: nothing calls out unless asked.

    ``assess_result`` requires an assessor argument, so this is enforced by the
    signature rather than by anyone remembering. The test pins the intent.
    """
    out = tmp_path / "report.pdf"
    result = service.review(
        str(FIXTURE),
        str(out),
        policy=GradingPolicy.default(),
        settings={"org_name": "Test Org", "org_short": "TST", "threshold": 90},
    )
    assert result.assessment is None
    sidecar = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert sidecar["assessment"] is None
