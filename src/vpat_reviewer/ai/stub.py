"""The deterministic assessor: builds the request, calls nothing, judges nothing."""

from __future__ import annotations

from vpat_reviewer.ai.base import (
    AssessmentError,
    AssessmentRequest,
    RiskAssessment,
)


class StubAssessor:
    """Satisfies the port without a model, a provider, or a network.

    It exists so the seam can be exercised end to end while the app stays
    offline, and it deliberately does **not** return a rubric category. The
    parser's rule is that a row with no evidence is not a finding; a category is
    the same rule with more at stake, because the verdict is the headline a
    reviewer acts on and nothing downstream could tell a stub's "Minor Changes"
    from a real one.

    So it reports the truth: nobody assessed this document.
    """

    model_id = "stub"

    def assess(self, request: AssessmentRequest) -> RiskAssessment:
        if not request.prompt.strip():
            # The only thing the stub can meaningfully check. A render() that
            # quietly produced nothing would otherwise look identical to a
            # working one, since neither returns a verdict.
            raise AssessmentError("The prompt is empty: nothing was asked.")
        return RiskAssessment.not_assessed(
            "No assessment model was called. This is the deterministic stub assessor: "
            "configure a model and a real adapter to get a verdict.",
            model_id=self.model_id,
        )
