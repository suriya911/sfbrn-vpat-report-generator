"""Impact rating — policy-driven, behavior-identical to v10 by default.

Combines reviewer answers (audience, access impact, legal exposure, deployment)
with the parsed barriers and the compliance score to suggest an overall impact
level (High / Medium / Low). All weights and thresholds come from the
:class:`GradingPolicy`; the explanatory prose stays here.

Returns the same ``{"suggested_level", "rationale"}`` dict the v10 GUI/report
already consume.
"""

from __future__ import annotations

from typing import TypedDict

from vpat_reviewer.domain.models import VPATCriterion
from vpat_reviewer.domain.policy import HIGH, Flag, GradingPolicy
from vpat_reviewer.domain.scoring import ScoreInfo

# Explanatory text tied to specific answer values (weights are editable in the
# policy; this descriptive prose is not part of the graded numbers).
_ACCESS_REASONS = {
    "denies_access": ("Reviewer determined this product denies access to users with disabilities."),
    "limits_some": (
        "Reviewer determined this product limits access for some users with disabilities."
    ),
}
_LEGAL_REASONS = {
    "high": "High legal exposure — ADA/Section 504 compliance risk is elevated.",
    "medium": "Medium legal exposure identified.",
}
_SCALE_REASONS = {
    2: (
        "Product is deployed campus-wide or serves 21+ users, amplifying the impact of any "
        "accessibility barrier."
    ),
    1: "Product serves a department or small team (2–20 users).",
}


class ImpactInfo(TypedDict):
    suggested_level: str
    rationale: list[str]


def calculate_impact(
    answers: dict[str, str],
    barriers: list[VPATCriterion],
    score_info: ScoreInfo | dict[str, object],
    policy: GradingPolicy | None = None,
) -> ImpactInfo:
    policy = policy or GradingPolicy.default()
    reasons: list[str] = []
    high_flags = 0
    medium_flags = 0

    def add(flag: Flag) -> None:
        nonlocal high_flags, medium_flags
        if flag.kind == HIGH:
            high_flags += flag.count
        else:
            medium_flags += flag.count

    audience = answers.get("audience", "individual")
    access = answers.get("access_impact", "no_limit")
    legal = answers.get("legal_exposure", "low")
    deploy = answers.get("deployment", "individual")
    score = score_info.get("score")

    # 1. Core functionality blocked by a fully-unsupported criterion.
    core_blocked = any(b.normalized_status == policy.core_block_status for b in barriers)
    if core_blocked:
        high_flags += 1
        reasons.append(
            "One or more WCAG Level AA criteria are fully unsupported, potentially "
            "blocking core functionality for users with disabilities."
        )

    # 2. Access impact.
    access_flag = policy.access_flags.get(access)
    if access_flag:
        add(access_flag)
        reasons.append(_ACCESS_REASONS.get(access, f"Access impact '{access}' raises the rating."))

    # 3. Scale (audience and deployment measure the same thing — combine as max,
    #    not sum, to avoid double-counting. v9 FIX G.)
    scale = max(policy.scale_weights.get(audience, 0), policy.scale_weights.get(deploy, 0))
    scale_flag = policy.scale_flags.get(scale)
    if scale_flag:
        add(scale_flag)
        reasons.append(
            _SCALE_REASONS.get(scale, f"Deployment scale level {scale} raises the rating.")
        )

    # 4. Legal exposure.
    legal_flag = policy.legal_flags.get(legal)
    if legal_flag:
        add(legal_flag)
        reasons.append(_LEGAL_REASONS.get(legal, f"Legal exposure '{legal}' raises the rating."))

    # 5. Score-based flags (first matching threshold, low → high).
    if isinstance(score, int):
        for sflag in sorted(policy.score_flags, key=lambda s: s.below):
            if score < sflag.below:
                add(Flag(sflag.kind, sflag.count))
                if sflag.kind == HIGH:
                    reasons.append(
                        f"Compliance score of {score}% (of reviewable criteria) "
                        f"indicates significant accessibility gaps."
                    )
                else:
                    reasons.append(
                        f"Compliance score of {score}% indicates moderate accessibility gaps."
                    )
                break

    # Decision.
    if high_flags >= policy.level_high_min_high_flags or (high_flags >= 1 and core_blocked):
        level = "High"
    elif high_flags == 1 or medium_flags >= policy.level_medium_min_medium_flags:
        level = "Medium"
    else:
        level = "Low"

    return ImpactInfo(suggested_level=level, rationale=reasons)
