"""Orchestration: the calls that tie the pipeline together.

* ``analyze()`` runs parse -> score -> impact (no file output).
* ``render_result()`` renders an existing analysis to a report file.
* ``review()`` is the convenience combination of the two.
* ``assess_result()`` asks an assessor to classify an analysis. You name the
  assessor; this module never picks one, and so never reaches for a network on
  its own.

The grading policy and organization settings default from the saved settings
store, so the CLI and GUI honor whatever the user configured. Pass explicit
values to override (tests do this for determinism).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vpat_reviewer.ai import prompt
from vpat_reviewer.ai.base import (
    AssessmentError,
    AssessmentRequest,
    RiskAssessment,
    RiskAssessor,
)
from vpat_reviewer.config import settings as settings_store
from vpat_reviewer.domain.impact import ImpactInfo, calculate_impact
from vpat_reviewer.domain.models import VPATCriterion, VPATDocument
from vpat_reviewer.domain.policy import GradingPolicy
from vpat_reviewer.domain.scoring import ScoreInfo, compliance_score, get_barriers
from vpat_reviewer.parsing import parse_vpat
from vpat_reviewer.reporting import ReportInputs, ReportLabRenderer, ReportRenderer


@dataclass
class ReviewResult:
    document: VPATDocument
    score: ScoreInfo
    impact: ImpactInfo
    barriers: list[VPATCriterion]
    answers: dict[str, str] = field(default_factory=dict)
    output_path: str | None = None
    json_path: str | None = None
    assessment: RiskAssessment | None = None

    @property
    def warnings(self) -> list[str]:
        return self.document.parse_warnings

    @property
    def has_criteria(self) -> bool:
        return bool(self.document.criteria)


def analyze(
    input_path: str,
    *,
    policy: GradingPolicy | None = None,
    answers: dict[str, str] | None = None,
) -> ReviewResult:
    """Parse a VPAT and compute its score, barriers, and suggested impact."""
    policy = policy or settings_store.load_policy()
    answers = answers or {}
    document = parse_vpat(input_path)
    score = compliance_score(document, policy)
    barriers = get_barriers(document, policy)
    impact = calculate_impact(answers, barriers, score, policy)
    return ReviewResult(
        document=document, score=score, impact=impact, barriers=barriers, answers=answers
    )


def render_result(
    result: ReviewResult,
    output_path: str,
    *,
    settings: dict[str, Any] | None = None,
    logo_path: str = "",
    renderer: ReportRenderer | None = None,
) -> ReviewResult:
    """Render an existing analysis to a report file."""
    if settings is None:
        settings = settings_store.load_settings()
    renderer = renderer or ReportLabRenderer()
    inputs = ReportInputs(
        document=result.document,
        score=dict(result.score),
        impact=dict(result.impact),
        answers=result.answers,
        logo_path=logo_path,
        settings=settings,
    )
    renderer.render(inputs, output_path)
    result.output_path = output_path
    return result


def to_dict(result: ReviewResult) -> dict[str, Any]:
    """Serialize a review to the machine-readable record of the whole pipeline.

    This is the single JSON shape the app emits -- for the CLI's ``--json`` and
    for the sidecar written beside a report -- and it is what a downstream
    consumer (including an LLM asked to interpret a vendor's claims) reads.

    Two things it deliberately carries beyond what the report shows:

    * ``document_kind`` says whether this was a VPAT at all. A consumer must be
      able to tell a vendor's conformance claim from a remediation plan or a
      blank template before it trusts a score.
    * every criterion keeps both ``raw_status`` (verbatim, as the vendor wrote
      it) and ``status`` (our canonical reading). Normalization is lossy and
      occasionally wrong, so the evidence travels next to the interpretation
      rather than being replaced by it.

    ``assessment`` is ``None`` unless ``assess_result`` ran. When present it is a
    model's verdict, and ``assessment.category`` may be ``"Not Assessed"`` --
    meaning a model was asked but produced nothing we could trust. Check it
    before treating the category as a judgment.
    """
    doc = result.document
    return {
        "document_kind": doc.document_kind.value,
        "document_kind_reasons": doc.document_kind_reasons,
        "product_name": doc.product_name,
        "product_version": doc.product_version,
        "product_description": doc.product_description,
        "product_type": doc.product_type,
        "vendor_name": doc.vendor_name,
        "vendor_contact": doc.vendor_contact,
        "vendor_report_date_raw": doc.vendor_report_date_raw,
        "vpat_edition": doc.vpat_edition,
        "is_outdated": doc.is_outdated,
        "outdated_note": doc.outdated_note,
        "standards_reviewed": doc.standards_reviewed,
        "evaluation_methods": doc.evaluation_methods,
        "score": result.score["score"],
        "supported": result.score["supported"],
        "reviewable_total": result.score["total"],
        "score_detail": dict(result.score),
        "impact_level": result.impact.get("suggested_level", ""),
        "impact": dict(result.impact),
        "barriers": [b.criterion_id for b in result.barriers],
        "criteria": [
            {
                "id": c.criterion_id,
                "title": c.title,
                "level": c.level,
                "raw_status": c.raw_status,
                "status": c.normalized_status,
                "remarks": c.remarks,
                "section": c.section,
            }
            for c in doc.criteria
        ],
        "warnings": result.warnings,
        "output_path": result.output_path,
        "assessment": result.assessment.to_dict() if result.assessment else None,
    }


def write_json(result: ReviewResult, output_path: str) -> str:
    """Write the normalized review JSON to ``output_path`` and return the path."""
    Path(output_path).write_text(
        json.dumps(to_dict(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result.json_path = output_path
    return output_path


def _record_for_prompt(result: ReviewResult) -> dict[str, Any]:
    """The record an assessor reads: everything ``to_dict`` emits except our verdict.

    Showing an assessor an ``assessment`` field tells it about the answer it is
    being asked for, and on a re-run it would be reading its own previous verdict
    and anchoring on it. The model judges the vendor's document, not our reading
    of it.
    """
    return {k: v for k, v in to_dict(result).items() if k != "assessment"}


def build_assessment_request(result: ReviewResult) -> AssessmentRequest:
    """The rubric with this review's record substituted in, ready to ask.

    Exposed separately from :func:`assess_result` so a caller can log exactly
    what was sent, or reuse one rendering across assessors.
    """
    record = _record_for_prompt(result)
    return AssessmentRequest(prompt=prompt.render(record), record=record)


def assess_result(
    result: ReviewResult,
    *,
    assessor: RiskAssessor,
    request: AssessmentRequest | None = None,
) -> ReviewResult:
    """Ask ``assessor`` to classify an existing analysis.

    ``assessor`` is required and has no default. There is no such thing as *the*
    assessor, and a default would mean this function decides on its own to reach
    for a network — so whoever wants a verdict names who gives it. That is also
    what keeps ``review()`` and ``make_demo.py`` offline: not a comment asking
    nicely, a signature.

    Never raises: an assessor that fails, or answers with something we cannot
    read as a verdict, costs the verdict and not the review.
    """
    model_id = getattr(assessor, "model_id", "")
    try:
        result.assessment = assessor.assess(request or build_assessment_request(result))
    except AssessmentError as e:
        result.assessment = RiskAssessment.not_assessed(
            "The assessor could not be asked, or its answer could not be read as a verdict.",
            model_id=model_id,
            error=str(e),
        )
    return result


def review(
    input_path: str,
    output_path: str,
    *,
    policy: GradingPolicy | None = None,
    answers: dict[str, str] | None = None,
    settings: dict[str, Any] | None = None,
    logo_path: str = "",
    renderer: ReportRenderer | None = None,
) -> ReviewResult:
    """Analyze a VPAT and render a report to ``output_path``."""
    result = analyze(input_path, policy=policy, answers=answers)
    render_result(result, output_path, settings=settings, logo_path=logo_path, renderer=renderer)
    write_json(result, str(Path(output_path).with_suffix(".json")))
    return result
