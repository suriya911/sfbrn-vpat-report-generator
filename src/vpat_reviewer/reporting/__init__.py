"""Reporting: render an analysis to an output file.

``ReportLabRenderer`` is the reference (PDF) implementation of the
:class:`ReportRenderer` port. Heavy layout code lives in ``reportlab_renderer``
and is imported lazily so importing this package doesn't pull in ReportLab until
a report is actually rendered.
"""

from __future__ import annotations

from typing import Any

from vpat_reviewer.reporting.base import ReportInputs, ReportRenderer

__all__ = [
    "ReportInputs",
    "ReportRenderer",
    "ReportLabRenderer",
    "OnePageRenderer",
    "renderer_for",
]


def renderer_for(settings: dict[str, Any] | None) -> ReportRenderer:
    """Pick the renderer the user configured (``report_style`` in settings.json).

    Unknown values fall back to the full report: a reviewer who fat-fingers the
    setting should get more of the review than they asked for, not less.
    """
    style = str((settings or {}).get("report_style", "full")).strip().lower()
    if style in ("one_page", "one-page", "onepage"):
        from vpat_reviewer.reporting.onepage import OnePageRenderer

        return OnePageRenderer()
    return ReportLabRenderer()


class ReportLabRenderer:
    """Renders a branded PDF via ReportLab (the reference renderer)."""

    output_suffix = ".pdf"

    def render(self, inputs: ReportInputs, output_path: str) -> None:
        from vpat_reviewer.reporting.reportlab_renderer import generate_report

        generate_report(  # type: ignore[no-untyped-call]
            inputs.document,
            inputs.score,
            inputs.impact,
            inputs.answers,
            output_path,
            logo_path=inputs.logo_path,
            settings=inputs.settings,
        )

    def validate(self, output_path: str) -> tuple[bool, list[str]]:
        """Post-generation validation: file exists, opens, has the required sections."""
        from vpat_reviewer.reporting.reportlab_renderer import validate_report

        ok, problems = validate_report(output_path)
        return bool(ok), list(problems)


def __getattr__(name: str) -> Any:
    """Expose OnePageRenderer without importing ReportLab at package import.

    onepage.py imports ReportLab at module level, so a plain top-level import
    here would undo the laziness this package promises (see the module
    docstring). ``from vpat_reviewer.reporting import OnePageRenderer`` still
    works -- it just pays for ReportLab at that moment rather than at startup.
    """
    if name == "OnePageRenderer":
        from vpat_reviewer.reporting.onepage import OnePageRenderer

        return OnePageRenderer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
