"""report_generator — compatibility shim (Phase 5 strangler).

The ReportLab PDF engine now lives in the ``vpat_reviewer.reporting`` package:
the layout code in ``reportlab_renderer`` and a ``ReportRenderer`` port +
``ReportLabRenderer`` adapter alongside it. This module re-exports the v10
functions so ``run_app.py`` and ``make_demo.py`` keep importing them unchanged.

New code should use the renderer class::

    from vpat_reviewer.reporting import ReportLabRenderer, ReportInputs
"""

from vpat_reviewer.reporting.reportlab_renderer import generate_report, validate_report

__all__ = ["generate_report", "validate_report"]
