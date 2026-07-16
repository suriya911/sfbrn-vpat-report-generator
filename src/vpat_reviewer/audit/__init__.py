"""The audit trail: one row per review, written where a human can read it.

An outbound port, the mirror of ``extraction/``: the core computes a review and
an adapter takes a record of it somewhere. ``CsvAuditLog`` is the adapter that
ships; another destination (SQLite, a network sink) means another class
satisfying :class:`AuditLog` and nothing else changes.

Two rules this package exists to keep:

- **A review must never fail because the log did.** Every adapter here swallows
  its own I/O errors. The report is the product; the log is bookkeeping, and
  bookkeeping that can take down a review is worse than no bookkeeping.
- **The log records, it never decides.** Nothing downstream reads it back.
"""

from __future__ import annotations

from vpat_reviewer.audit.base import FIELDS, AuditEvent, AuditLog
from vpat_reviewer.audit.csv_log import CsvAuditLog, default_log_path, log_for

__all__ = [
    "FIELDS",
    "AuditEvent",
    "AuditLog",
    "CsvAuditLog",
    "default_log_path",
    "log_for",
]
