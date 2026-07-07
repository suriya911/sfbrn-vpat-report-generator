"""Reporting: render an analysis to an output file.

``ReportLabRenderer`` is the reference (PDF) implementation of the
:class:`ReportRenderer` port. Heavy layout code lives in ``reportlab_renderer``
and is imported lazily so importing this package doesn't pull in ReportLab until
a report is actually rendered.
"""

from __future__ import annotations

from vpat_reviewer.reporting.base import ReportInputs, ReportRenderer

__all__ = ["ReportInputs", "ReportRenderer", "ReportLabRenderer"]


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
