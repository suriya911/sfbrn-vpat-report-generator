"""Ask a model to classify a parsed VPAT's accessibility risk.

The pipeline: ``service.to_dict()`` produces the record, ``prompt.render()`` puts
it into the rubric, a :class:`RiskAssessor` answers, and ``response.parse()``
reads that answer back into a :class:`RiskAssessment`.

``BedrockAssessor`` is the adapter that ships, and the app uses it by default
(``use_ai`` in settings.json). ``StubAssessor`` calls nothing and is the test
double. Another provider is a new class satisfying the port; see
``docs/extending.md``.

:mod:`vpat_reviewer.ai.bedrock` is deliberately **not** re-exported here:
importing this package must not require boto3 or reach for AWS credentials.
Import the adapter explicitly, from the composition root that chose it.
"""

from __future__ import annotations

from vpat_reviewer.ai.base import (
    CATEGORIES,
    NOT_ASSESSED,
    RISK_LEVELS,
    AssessmentError,
    AssessmentRequest,
    RegulatoryBasis,
    RiskAssessment,
    RiskAssessor,
)
from vpat_reviewer.ai.stub import StubAssessor

__all__ = [
    "CATEGORIES",
    "NOT_ASSESSED",
    "RISK_LEVELS",
    "AssessmentError",
    "AssessmentRequest",
    "RegulatoryBasis",
    "RiskAssessment",
    "RiskAssessor",
    "StubAssessor",
]
