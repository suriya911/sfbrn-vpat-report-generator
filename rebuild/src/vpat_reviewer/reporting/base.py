"""The reporting port: what any report renderer receives, and the interface.

A renderer turns an analysis into an output file. The ReportLab PDF renderer is
the reference implementation; adding an HTML or DOCX renderer means writing
another class that satisfies :class:`ReportRenderer` — nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from vpat_reviewer.domain.models import VPATDocument


@dataclass
class ReportInputs:
    """Everything a renderer needs to produce a report."""

    document: VPATDocument
    score: dict[str, Any]  # ScoreInfo
    impact: dict[str, Any]  # ImpactInfo (may include a reviewer-confirmed "final_level")
    answers: dict[str, str]
    logo_path: str = ""
    settings: dict[str, Any] | None = None


@runtime_checkable
class ReportRenderer(Protocol):
    """Renders a :class:`ReportInputs` to a file at ``output_path``."""

    #: The file extension this renderer produces, e.g. ".pdf".
    output_suffix: str

    def render(self, inputs: ReportInputs, output_path: str) -> None: ...
