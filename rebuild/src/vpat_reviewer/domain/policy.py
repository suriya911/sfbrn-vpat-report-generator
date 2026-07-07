"""The editable VPAT grading policy.

This module is the answer to the requirement "the VPAT grading system needs to
be editable". Every decision the grader makes — which statuses count as a pass,
which are excluded from the denominator, the score-band cutoffs and their
messages, the compliance threshold, and the impact-rating weights/thresholds —
is expressed here as *data* on a frozen dataclass, not as constants buried in
functions.

* ``GradingPolicy.default()`` reproduces the v10 behavior exactly.
* ``to_dict()`` / ``from_dict()`` round-trip through JSON so a policy can be
  saved in settings and edited by the user (via CLI now, GUI in Phase 7).
* ``from_dict()`` merges over defaults, so a settings file may override just one
  knob and inherit the rest.

Editing is functional: helpers return a *new* policy (via ``dataclasses.replace``)
rather than mutating in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

HIGH = "high"
MEDIUM = "medium"


@dataclass(frozen=True)
class Flag:
    """A weighted contribution to an impact rating (``kind`` is 'high'|'medium')."""

    kind: str
    count: int


@dataclass(frozen=True)
class ScoreFlag:
    """Add ``flag`` when the compliance score is strictly below ``below``."""

    below: int
    kind: str
    count: int


@dataclass(frozen=True)
class ScoreBand:
    """A labeled band applied when ``score >= min_score`` (bands tested high→low)."""

    min_score: int
    label: str
    message: str


DEFAULT_SCORE_BANDS: tuple[ScoreBand, ...] = (
    ScoreBand(
        90,
        "Strong",
        "Strong accessibility support. The submitted VPAT indicates broad WCAG Level AA "
        "support, with few or no identified Level AA barriers.",
    ),
    ScoreBand(
        75,
        "Moderate",
        "Moderate accessibility support. The submitted VPAT indicates general WCAG Level AA "
        "support, but some barriers or exceptions may require review before approval.",
    ),
    ScoreBand(
        50,
        "Limited",
        "Limited accessibility support. The submitted VPAT includes multiple Level AA barriers "
        "or incomplete support statements that should be reviewed before adoption.",
    ),
    ScoreBand(
        0,
        "High risk",
        "High accessibility risk. The submitted VPAT indicates significant WCAG Level AA "
        "barriers, missing information, or limited accessibility support.",
    ),
)


def _default_scale_weights() -> dict[str, int]:
    return {"individual": 0, "department": 1, "small_team": 1, "campus_wide": 2}


def _default_access_flags() -> dict[str, Flag]:
    return {"denies_access": Flag(HIGH, 2), "limits_some": Flag(MEDIUM, 1)}


def _default_legal_flags() -> dict[str, Flag]:
    return {"high": Flag(HIGH, 1), "medium": Flag(MEDIUM, 1)}


def _default_scale_flags() -> dict[int, Flag]:
    # Keyed by the scale weight produced by ``scale_weights``.
    return {2: Flag(HIGH, 1), 1: Flag(MEDIUM, 1)}


def _default_score_flags() -> tuple[ScoreFlag, ...]:
    return (ScoreFlag(60, HIGH, 1), ScoreFlag(75, MEDIUM, 1))


@dataclass(frozen=True)
class GradingPolicy:
    # ── Scoring ──────────────────────────────────────────────────────────────
    graded_level: str = "AA"
    #: Statuses that count as a pass in the numerator.
    supported_statuses: tuple[str, ...] = ("Supports",)
    #: Statuses excluded from the denominator (feature absent → cannot pass/fail).
    excluded_statuses: tuple[str, ...] = ("Not Applicable",)
    #: The pass/fail line shown in the report.
    compliance_threshold: int = 90
    #: Bands applied to the final score, tested from highest ``min_score`` down.
    score_bands: tuple[ScoreBand, ...] = DEFAULT_SCORE_BANDS

    # ── Impact rating ────────────────────────────────────────────────────────
    #: A barrier with this status forces a high-severity flag ("core blocked").
    core_block_status: str = "Does Not Support"
    #: Deployment/audience label → scale weight.
    scale_weights: dict[str, int] = field(default_factory=_default_scale_weights)
    #: access_impact answer → flag.
    access_flags: dict[str, Flag] = field(default_factory=_default_access_flags)
    #: legal_exposure answer → flag.
    legal_flags: dict[str, Flag] = field(default_factory=_default_legal_flags)
    #: resulting scale weight → flag.
    scale_flags: dict[int, Flag] = field(default_factory=_default_scale_flags)
    #: score-based flags (below threshold → flag).
    score_flags: tuple[ScoreFlag, ...] = field(default_factory=_default_score_flags)
    #: Decision thresholds on accumulated flags.
    level_high_min_high_flags: int = 2
    level_medium_min_medium_flags: int = 2

    # ── Construction ─────────────────────────────────────────────────────────
    @classmethod
    def default(cls) -> GradingPolicy:
        return cls()

    def with_changes(self, **changes: Any) -> GradingPolicy:
        """Return a new policy with the given fields replaced."""
        return replace(self, **changes)

    # ── Scoring helpers ──────────────────────────────────────────────────────
    def is_supported(self, status: str) -> bool:
        return status in self.supported_statuses

    def is_excluded(self, status: str) -> bool:
        return status in self.excluded_statuses

    def is_barrier(self, status: str) -> bool:
        """A reviewable, non-passing status for a graded criterion."""
        return not self.is_supported(status) and not self.is_excluded(status)

    def band_for(self, score: int) -> ScoreBand:
        """The first band (highest cutoff first) whose ``min_score`` the score meets."""
        for band in sorted(self.score_bands, key=lambda b: b.min_score, reverse=True):
            if score >= band.min_score:
                return band
        # Guaranteed non-empty by validate(); fall back to the lowest band.
        return min(self.score_bands, key=lambda b: b.min_score)

    # ── Validation ───────────────────────────────────────────────────────────
    def validate(self) -> list[str]:
        """Return a list of human-readable problems; empty means valid."""
        problems: list[str] = []
        if not self.graded_level:
            problems.append("graded_level must not be empty.")
        if not self.supported_statuses:
            problems.append("supported_statuses must list at least one status.")
        if not self.score_bands:
            problems.append("score_bands must define at least one band.")
        if not any(b.min_score <= 0 for b in self.score_bands):
            problems.append("score_bands must include a catch-all band with min_score <= 0.")
        if not 0 <= self.compliance_threshold <= 100:
            problems.append("compliance_threshold must be between 0 and 100.")
        return problems

    # ── Serialization (JSON-friendly) ────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        def flag(f: Flag) -> dict[str, Any]:
            return {"kind": f.kind, "count": f.count}

        return {
            "graded_level": self.graded_level,
            "supported_statuses": list(self.supported_statuses),
            "excluded_statuses": list(self.excluded_statuses),
            "compliance_threshold": self.compliance_threshold,
            "score_bands": [
                {"min_score": b.min_score, "label": b.label, "message": b.message}
                for b in self.score_bands
            ],
            "core_block_status": self.core_block_status,
            "scale_weights": dict(self.scale_weights),
            "access_flags": {k: flag(v) for k, v in self.access_flags.items()},
            "legal_flags": {k: flag(v) for k, v in self.legal_flags.items()},
            "scale_flags": {str(k): flag(v) for k, v in self.scale_flags.items()},
            "score_flags": [
                {"below": s.below, "kind": s.kind, "count": s.count} for s in self.score_flags
            ],
            "level_high_min_high_flags": self.level_high_min_high_flags,
            "level_medium_min_medium_flags": self.level_medium_min_medium_flags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GradingPolicy:
        """Build a policy from a (possibly partial) dict, inheriting defaults."""
        base = cls.default()
        if not data:
            return base

        def flag(d: Any, fallback: Flag) -> Flag:
            if isinstance(d, dict) and "kind" in d and "count" in d:
                return Flag(str(d["kind"]), int(d["count"]))
            return fallback

        kwargs: dict[str, Any] = {}
        if "graded_level" in data:
            kwargs["graded_level"] = str(data["graded_level"])
        if "supported_statuses" in data:
            kwargs["supported_statuses"] = tuple(data["supported_statuses"])
        if "excluded_statuses" in data:
            kwargs["excluded_statuses"] = tuple(data["excluded_statuses"])
        if "compliance_threshold" in data:
            kwargs["compliance_threshold"] = int(data["compliance_threshold"])
        if "score_bands" in data and data["score_bands"]:
            kwargs["score_bands"] = tuple(
                ScoreBand(int(b["min_score"]), str(b["label"]), str(b["message"]))
                for b in data["score_bands"]
            )
        if "core_block_status" in data:
            kwargs["core_block_status"] = str(data["core_block_status"])
        if "scale_weights" in data:
            kwargs["scale_weights"] = {str(k): int(v) for k, v in data["scale_weights"].items()}
        if "access_flags" in data:
            kwargs["access_flags"] = {
                k: flag(v, Flag(MEDIUM, 1)) for k, v in data["access_flags"].items()
            }
        if "legal_flags" in data:
            kwargs["legal_flags"] = {
                k: flag(v, Flag(MEDIUM, 1)) for k, v in data["legal_flags"].items()
            }
        if "scale_flags" in data:
            kwargs["scale_flags"] = {
                int(k): flag(v, Flag(MEDIUM, 1)) for k, v in data["scale_flags"].items()
            }
        if "score_flags" in data:
            kwargs["score_flags"] = tuple(
                ScoreFlag(int(s["below"]), str(s["kind"]), int(s["count"]))
                for s in data["score_flags"]
            )
        if "level_high_min_high_flags" in data:
            kwargs["level_high_min_high_flags"] = int(data["level_high_min_high_flags"])
        if "level_medium_min_medium_flags" in data:
            kwargs["level_medium_min_medium_flags"] = int(data["level_medium_min_medium_flags"])
        return replace(base, **kwargs)
