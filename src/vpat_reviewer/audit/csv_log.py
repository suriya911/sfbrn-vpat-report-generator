"""The CSV audit log: one row per review, appended to a file reviewers can open.

CSV and not JSON because the reader is a person with Excel, not a program. That
choice is what drives the rest of this module: a header written once, columns
that never move (see :data:`~vpat_reviewer.audit.base.FIELDS`), and cells that
are safe to open in a spreadsheet.
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Any

from vpat_reviewer.audit.base import FIELDS, AuditEvent
from vpat_reviewer.config.settings import user_files_dir

logger = logging.getLogger(__name__)

#: The file name inside the log folder.
LOG_NAME = "vpat_review_log.csv"

#: Env override for the log's location, mirroring VPAT_SETTINGS_PATH and the
#: VPAT_BEDROCK_* vars: it retargets one machine (or one test run) without
#: touching settings.json. It wins over the setting because the setting is
#: committed and shared, while this is local by nature.
#:
#: The tests set it. Without it, anything that drives a review -- including the
#: CLI test suite -- appends fixture rows to the developer's own real log,
#: which is real data a reviewer is meant to audit.
PATH_ENV = "VPAT_AUDIT_LOG_PATH"

# Leading characters Excel and LibreOffice read as the start of a formula. A
# vendor product literally named "=Acme" is enough for a cell to be *executed*
# rather than displayed when a reviewer opens the log -- the CSV injection
# problem. Vendor text reaches this file (product names, error strings), and it
# is no more trustworthy here than it is in the PDF (§6, _esc).
_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def default_log_path() -> Path:
    """Where the log lives when nothing says otherwise.

    Inside the same ``~/Downloads/VPAT Reviewer Files`` the GUI writes reports
    to -- one folder to look in, one folder to hand over. The location comes
    from ``config.settings.user_files_dir`` rather than being spelled out here,
    so the log cannot drift away from the reports it describes.
    """
    override = os.environ.get(PATH_ENV, "").strip()
    if override:
        return Path(override)
    return user_files_dir() / LOG_NAME


def _defuse(value: str) -> str:
    """Make a cell safe to open in a spreadsheet without changing what it says.

    A leading apostrophe is the conventional escape: Excel shows the original
    text and does not evaluate it. Quoting alone would not help -- the CSV
    quoting is stripped before the formula parser ever sees the cell.
    """
    if value.startswith(_FORMULA_LEAD):
        return "'" + value
    return value


class CsvAuditLog:
    """Appends one row per review. Satisfies the AuditLog port.

    Never raises. A locked file (the reviewer has the log open in Excel -- the
    normal case, not an edge case), a full disk, or a read-only folder must cost
    the row and not the review.
    """

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path else default_log_path()

    def record(self, event: AuditEvent) -> None:
        row = {k: _defuse(v) for k, v in event.to_row().items()}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Header only for a file that does not exist yet or is empty: an
            # existing log is appended to, never re-headed.
            new = not self.path.exists() or self.path.stat().st_size == 0
            # newline="" is required by csv on Windows; without it every row is
            # followed by a blank one.
            with open(self.path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
                if new:
                    writer.writeheader()
                writer.writerow(row)
        except Exception as e:  # noqa: BLE001 - the log must never break a review
            logger.warning("Could not write the audit log at %s: %s", self.path, e)


def log_for(settings: dict[str, Any] | None) -> CsvAuditLog | None:
    """The log the settings ask for, or ``None`` when logging is switched off.

    Mirrors ``reporting.renderer_for``: the composition root reads the setting,
    the core never does. Returning ``None`` rather than a no-op writer keeps
    "logging is off" a visible decision at the call site.

    Precedence is ``VPAT_AUDIT_LOG_PATH`` > the setting > the default;
    the env var wins because it is the local, per-machine lever and the setting
    ships to everyone.
    """
    cfg = settings or {}
    if not cfg.get("audit_log_enabled", True):
        return None
    if os.environ.get(PATH_ENV, "").strip():
        return CsvAuditLog(None)  # default_log_path() reads the override
    return CsvAuditLog(str(cfg.get("audit_log_path") or "") or None)
