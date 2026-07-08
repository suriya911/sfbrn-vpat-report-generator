"""Orchestration: the calls that tie the pipeline together.

* ``analyze()`` runs parse -> score -> impact (no file output).
* ``render_result()`` renders an existing analysis to a report file.
* ``review()`` is the convenience combination of the two.

The grading policy and organization settings default from the saved settings
store, so the CLI and GUI honor whatever the user configured. Pass explicit
values to override (tests do this for determinism).
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    return render_result(
        result, output_path, settings=settings, logo_path=logo_path, renderer=renderer
    )
