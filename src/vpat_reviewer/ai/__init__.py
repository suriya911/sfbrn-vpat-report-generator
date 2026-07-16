"""AI review adapter (outermost layer).

Sends the parsed, scored VPAT to Amazon Bedrock and turns the model's answer
into a verdict + narrative the report renderer can consume. This layer is
optional: with ``use_ai=False`` (or on any Bedrock failure) the app falls back
to the deterministic pipeline and stays fully offline.

Depends inward on :mod:`vpat_reviewer.service`; nothing in the domain core
depends on this package.
"""

from __future__ import annotations

from vpat_reviewer.ai.bedrock import BedrockConfig, BedrockError, invoke
from vpat_reviewer.ai.review import AIReview, review_with_ai

__all__ = [
    "AIReview",
    "BedrockConfig",
    "BedrockError",
    "invoke",
    "review_with_ai",
]
