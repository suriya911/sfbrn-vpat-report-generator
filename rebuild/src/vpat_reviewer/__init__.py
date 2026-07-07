"""vpat_reviewer — offline VPAT accessibility-compliance review.

Library-first architecture (ports & adapters). The pure domain lives in
``vpat_reviewer.domain`` and depends on nothing external. Everything else —
document extraction, WCAG reference data, PDF rendering, the GUI — are adapters
around it.

Public API grows as phases land. Today it exposes the domain building blocks and
the version. Orchestration (`review()`) and the CLI arrive in Phase 6.
"""

from vpat_reviewer.domain.models import VPATCriterion, VPATDocument
from vpat_reviewer.domain.policy import GradingPolicy, ScoreBand

__version__ = "11.0.0"

__all__ = [
    "VPATCriterion",
    "VPATDocument",
    "GradingPolicy",
    "ScoreBand",
    "__version__",
]
