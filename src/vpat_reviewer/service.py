"""Orchestration: the calls that tie the pipeline together.

* ``analyze()`` runs parse -> score -> impact (no file output).
* ``render_result()`` renders an existing analysis to a report file.
* ``review()`` is the convenience combination of the two.

The grading policy and organization settings default from the saved settings
store, so the CLI and GUI honor whatever the user configured. Pass explicit
values to override (tests do this for determinism).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    }


def write_json(result: ReviewResult, output_path: str) -> str:
    """Write the normalized review JSON to ``output_path`` and return the path."""
    Path(output_path).write_text(
        json.dumps(to_dict(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result.json_path = output_path
    return output_path


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
