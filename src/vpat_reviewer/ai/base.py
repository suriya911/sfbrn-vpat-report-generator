"""The assessment boundary: what a risk assessor is asked, and what it answers.

An assessor turns a rendered prompt into a categorical verdict on a vendor's
VPAT. ``BedrockAssessor`` is the one that ships; ``StubAssessor`` is the
reference implementation and the test double. Another provider means another
class satisfying :class:`RiskAssessor` — nothing else changes.

Nothing here knows about a model, a provider, or a network. That is the point:
the seam exists so the network lives on the far side of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from vpat_reviewer.domain.verdict import CATEGORIES

__all__ = [
    "CATEGORIES",
    "NOT_ASSESSED",
    "RISK_LEVELS",
    "AssessmentError",
    "AssessmentRequest",
    "RegulatoryBasis",
    "RiskAssessment",
    "RiskAssessor",
    "TokenUsage",
]

#: The risk levels the rubric allows.
RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High", "Critical", "Unknown")

# Not a rubric category, and deliberately outside CATEGORIES: this is the verdict
# when no model ran or its answer could not be trusted. Keeping it out of the
# allowed set means it can never be mistaken for a judgment, and means an
# assessor cannot mint one (``response.parse`` rejects it on input).
NOT_ASSESSED = "Not Assessed"


class AssessmentError(Exception):
    """An assessor could not be asked, or its answer could not be read."""


@dataclass(frozen=True)
class AssessmentRequest:
    """Everything an assessor needs to produce a verdict."""

    #: The fully rendered prompt, review record already substituted in.
    prompt: str
    #: The record the prompt was built from, for adapters that need it apart
    #: from the prose (structured tool-use, say, rather than a text completion).
    record: dict[str, Any]


@dataclass(frozen=True)
class TokenUsage:
    """What one assessment cost, as the provider reported it.

    This is transport metadata, not model output: it comes from the response
    envelope, never from the text the model wrote. That distinction is the whole
    reason it is a separate object — a model cannot report its own token usage,
    and a number it volunteered would be a claim, not a measurement.

    An assessor that reports no usage yields ``None`` rather than an instance of
    zeros: "not reported" and "cost nothing" are different facts, and a log that
    conflates them is a log that invents a measurement (golden rule 7, one layer
    out).
    """

    input_tokens: int
    output_tokens: int
    #: Wall-clock latency the provider reported, if any.
    latency_ms: int | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True)
class RegulatoryBasis:
    """Which obligations the verdict leans on."""

    ada_relevance: str = ""
    section_508_relevance: str = ""
    wcag_relevance: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "ada_relevance": self.ada_relevance,
            "section_508_relevance": self.section_508_relevance,
            "wcag_relevance": self.wcag_relevance,
        }


@dataclass(frozen=True)
class RiskAssessment:
    """One assessor's verdict on one VPAT.

    ``raw_response`` travels beside the parsed fields for the same reason
    ``raw_status`` travels beside ``status`` on a criterion: our reading of an
    assessor is lossy and occasionally wrong, so the evidence has to survive
    next to the interpretation rather than be replaced by it.
    """

    category: str
    risk_level: str = "Unknown"
    confidence: float = 0.0
    reason: str = ""
    regulatory_basis: RegulatoryBasis = field(default_factory=RegulatoryBasis)
    signals_found: tuple[str, ...] = ()
    major_accessibility_risks: tuple[str, ...] = ()
    missing_or_unclear_information: tuple[str, ...] = ()
    recommendation: str = ""
    next_steps: tuple[str, ...] = ()
    needs_human_review: bool = True
    #: What produced this verdict. Empty when nothing did.
    model_id: str = ""
    #: Why there is no verdict. Empty on a successful assessment.
    error: str = ""
    #: The assessor's literal output, unparsed.
    raw_response: str = ""
    #: What the call cost, as the provider reported it. ``None`` when unreported
    #: -- including on a failed call, which may still have burned input tokens
    #: we were never told about.
    usage: TokenUsage | None = None

    @classmethod
    def not_assessed(
        cls,
        reason: str,
        *,
        model_id: str = "",
        error: str = "",
        raw_response: str = "",
    ) -> RiskAssessment:
        """The honest non-verdict: no category, no confidence, human required.

        Used when no assessor ran, when one is misconfigured, and when one
        answered with something we could not read. In every case the truthful
        report is that nobody judged this document — not a plausible guess.
        """
        return cls(
            category=NOT_ASSESSED,
            risk_level="Unknown",
            confidence=0.0,
            reason=reason,
            needs_human_review=True,
            model_id=model_id,
            error=error,
            raw_response=raw_response,
        )

    @property
    def is_verdict(self) -> bool:
        """Whether an assessor actually classified this document."""
        return self.category in CATEGORIES

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape a downstream consumer reads."""
        return {
            "category": self.category,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "reason": self.reason,
            "regulatory_basis": self.regulatory_basis.to_dict(),
            "signals_found": list(self.signals_found),
            "major_accessibility_risks": list(self.major_accessibility_risks),
            "missing_or_unclear_information": list(self.missing_or_unclear_information),
            "recommendation": self.recommendation,
            "next_steps": list(self.next_steps),
            "needs_human_review": self.needs_human_review,
            "model_id": self.model_id,
            "error": self.error,
            "raw_response": self.raw_response,
            "usage": self.usage.to_dict() if self.usage else None,
        }


@runtime_checkable
class RiskAssessor(Protocol):
    """Answers an :class:`AssessmentRequest` with a :class:`RiskAssessment`."""

    #: Identifies what produces the verdict, e.g. "stub" or a provider's model id.
    model_id: str

    def assess(self, request: AssessmentRequest) -> RiskAssessment: ...
