"""The audit port: what one review looks like on the record, and the interface.

An :class:`AuditEvent` is a flat row of strings on purpose. The log is read by
reviewers in Excel, not by this app -- nothing downstream parses it back -- so
the schema is optimized for someone scanning a column, and nested structure has
no reader to serve.

**A field is empty when we do not know it, never guessed.** That is golden rule 7
one layer out: a log that fills in a plausible zero is a log that manufactures
evidence about a review that a human may later rely on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

#: The column order, and the whole schema. Append to the end -- never reorder or
#: remove: an existing CSV on a reviewer's machine has already been written with
#: this header, and a spreadsheet opened against a shuffled schema silently reads
#: the wrong values under the right headings.
FIELDS: tuple[str, ...] = (
    "timestamp",
    "app_version",
    # What was reviewed. The digest identifies the exact bytes: two reviews of
    # "the same" document are only the same review if this matches.
    "source_path",
    "source_sha256",
    "source_bytes",
    "document_kind",
    "product_name",
    "vendor_name",
    "product_version",
    "vendor_report_date",
    # Parser health. `unresolved_criteria` is the corpus scoreboard's `unres`
    # column per run: a document that quietly stopped parsing shows up here as a
    # high count next to an authoritative-looking score (see CLAUDE.md §7a).
    "criteria_total",
    "unresolved_criteria",
    "parse_warnings",
    # The score and the policy that produced it.
    "score",
    "supported",
    "reviewable",
    "na_excluded",
    "threshold",
    "barriers_total",
    "barrier_ids",
    # The reviewer's impact answers -- the inputs that outrank the score in
    # classify_report, so a verdict cannot be re-derived from this row without
    # them.
    "audience",
    "access_impact",
    "legal_exposure",
    "deployment",
    "impact_suggested",
    "impact_final",
    # The verdict, and who said it. `verdict_source` is the load-bearing column:
    # "ai" and "offline" are different claims about the same string.
    "verdict",
    "verdict_source",
    "ai_category",
    "ai_risk_level",
    "ai_confidence",
    "ai_needs_human_review",
    "ai_model_id",
    "ai_error",
    # What the call cost. Empty (not 0) when the provider reported nothing.
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_ms",
    # Where everything landed, so a row leads back to the evidence.
    "report_path",
    "report_style",
    "json_path",
    "ai_response_path",
    # Who ran it.
    "reviewer_name",
    "org_name",
)


@dataclass(frozen=True)
class AuditEvent:
    """One review, as it goes on the record.

    Every field defaults to empty: a caller that does not know something leaves
    it alone rather than inventing a value for it.
    """

    values: dict[str, str] = field(default_factory=dict)

    def to_row(self) -> dict[str, str]:
        """The row, with every column present and unknown ones empty."""
        return {name: self.values.get(name, "") for name in FIELDS}

    @classmethod
    def of(cls, **values: Any) -> AuditEvent:
        """Build an event, dropping unknowns and stringifying the rest.

        ``None`` becomes an empty cell rather than the string "None" -- the
        difference between "not reported" and a value that says nothing.
        """
        unknown = set(values) - set(FIELDS)
        if unknown:
            raise ValueError(f"Not audit-log columns: {sorted(unknown)}")
        return cls({k: "" if v is None else str(v) for k, v in values.items()})


@runtime_checkable
class AuditLog(Protocol):
    """Records an :class:`AuditEvent`. Must never raise."""

    def record(self, event: AuditEvent) -> None: ...
