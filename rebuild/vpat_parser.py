"""vpat_parser — compatibility shim (Phase 2 strangler).

All parsing, extraction, scoring, and impact logic now lives in the
``vpat_reviewer`` package (fully typed and unit-tested). This module re-exports
the v10 public names so ``run_app.py``, ``make_demo.py``, and the regression
tests keep importing ``from vpat_parser import ...`` unchanged.

New code should import from the package directly, e.g.::

    from vpat_reviewer.parsing import parse_vpat
    from vpat_reviewer.domain.scoring import compliance_score, get_barriers
"""

from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.models import VPATCriterion, VPATData
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.domain.scoring import compliance_score, get_barriers
from vpat_reviewer.parsing import parse_vpat

# Legacy name for the barrier selector.
get_aa_barriers = get_barriers

__all__ = [
    "VPATCriterion",
    "VPATData",
    "normalize_status",
    "parse_vpat",
    "compliance_score",
    "get_barriers",
    "get_aa_barriers",
    "calculate_impact",
]
