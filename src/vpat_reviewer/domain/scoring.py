"""Compliance scoring — policy-driven, behavior-identical to v10 by default.

Returns the same dict shape the v10 report generator and GUI already consume, so
this can be dropped in behind the legacy ``compliance_score`` without touching
callers. The scoring *rules* now come from a :class:`GradingPolicy`.
"""

from __future__ import annotations

from typing import TypedDict

from vpat_reviewer.domain.models import VPATCriterion, VPATDocument
from vpat_reviewer.domain.policy import GradingPolicy


class ScoreInfo(TypedDict):
    score: int | None
    supported: int
    total: int
    #: Criteria found at the graded levels (A + AA by default). The key name
    #: predates cumulative grading and is kept for report/sidecar compatibility.
    total_aa_found: int
    na_excluded: int
    message: str


def graded_criteria(document: VPATDocument, policy: GradingPolicy) -> list[VPATCriterion]:
    """Criteria at the policy's conformance target (default "AA": Levels A and AA).

    The target is cumulative, matching WCAG's own conformance model — a Level AA
    claim asserts every Level A and Level AA criterion.
    """
    return [c for c in document.criteria if c.level in policy.graded_levels]


def get_barriers(
    document: VPATDocument, policy: GradingPolicy | None = None
) -> list[VPATCriterion]:
    """Graded criteria that are neither supported nor excluded.

    By default: Level A and AA criteria that are not fully "Supports", excluding
    "Not Applicable" (feature absent → no barrier to report). Includes Partially
    Supports, Does Not Support, and Not Evaluated.
    """
    policy = policy or GradingPolicy.default()
    return [
        c
        for c in document.criteria
        if c.level in policy.graded_levels and policy.is_barrier(c.normalized_status)
    ]


def compliance_score(document: VPATDocument, policy: GradingPolicy | None = None) -> ScoreInfo:
    """Score = supported / (graded − excluded) × 100.

    Excluded statuses (default: Not Applicable) are removed from the denominator
    because the feature is not present — it cannot logically pass or fail.
    Not Evaluated remains in the denominator (it was assessed, just not scored).
    """
    policy = policy or GradingPolicy.default()
    graded = graded_criteria(document, policy)
    reviewed = [c for c in graded if not policy.is_excluded(c.normalized_status)]
    total = len(reviewed)

    if total == 0:
        return ScoreInfo(
            score=None,
            supported=0,
            total=0,
            total_aa_found=len(graded),
            na_excluded=len(graded) - total,
            message=(
                "Compliance score could not be calculated — no reviewable "
                "WCAG criteria were found at the graded levels."
            ),
        )

    supported = sum(1 for c in reviewed if policy.is_supported(c.normalized_status))
    score = round(supported / total * 100)
    band = policy.band_for(score)

    return ScoreInfo(
        score=score,
        supported=supported,
        total=total,
        total_aa_found=len(graded),
        na_excluded=len(graded) - total,
        message=band.message,
    )
