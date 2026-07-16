"""What a review looks like on the record: service.build_audit_event."""

from __future__ import annotations

from pathlib import Path

from vpat_reviewer.ai.base import RiskAssessment, TokenUsage
from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.models import VPATCriterion, VPATDocument
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.domain.scoring import compliance_score, get_barriers
from vpat_reviewer.service import ReviewResult, build_audit_event

ANSWERS = {
    "audience": "campus_wide",
    "access_impact": "limits_some",
    "legal_exposure": "medium",
    "deployment": "campus_wide",
}
SETTINGS = {"org_name": "SFBRN", "reviewer_name": "A. Reviewer", "threshold": 90}


def _result() -> ReviewResult:
    doc = VPATDocument(product_name="TestProduct", vendor_name="Vendor Inc")
    doc.criteria = [
        VPATCriterion("1.1.1", "Non-text Content", "AA", "Supports", normalize_status("Supports")),
        VPATCriterion(
            "1.4.3", "Contrast", "AA", "Does Not Support", normalize_status("Does Not Support")
        ),
    ]
    score = compliance_score(doc)
    barriers = get_barriers(doc)
    return ReviewResult(
        document=doc,
        score=score,
        impact=calculate_impact(ANSWERS, barriers, score),
        barriers=barriers,
        answers=ANSWERS,
    )


def test_the_event_carries_the_score_and_the_answers() -> None:
    row = build_audit_event(_result(), settings=SETTINGS).to_row()

    assert row["product_name"] == "TestProduct"
    assert row["score"] == "50"
    assert row["barriers_total"] == "1"
    assert row["barrier_ids"] == "1.4.3"
    assert row["audience"] == "campus_wide"
    assert row["legal_exposure"] == "medium"
    assert row["threshold"] == "90"
    assert row["reviewer_name"] == "A. Reviewer"


def test_token_usage_reaches_the_row() -> None:
    result = _result()
    result.assessment = RiskAssessment(
        category="Minor Issue",
        model_id="a-model",
        confidence=0.8,
        usage=TokenUsage(input_tokens=5100, output_tokens=420, latency_ms=3300),
    )
    row = build_audit_event(result, settings=SETTINGS, verdict_source="ai").to_row()

    assert (row["input_tokens"], row["output_tokens"], row["total_tokens"]) == (
        "5100",
        "420",
        "5520",
    )
    assert row["latency_ms"] == "3300"
    assert row["ai_model_id"] == "a-model"
    assert row["verdict_source"] == "ai"


def test_an_assessment_without_usage_leaves_the_token_cells_empty() -> None:
    """A model that reported no usage must not be logged as having cost zero."""
    result = _result()
    result.assessment = RiskAssessment(category="Minor Issue", model_id="a-model")
    row = build_audit_event(result, settings=SETTINGS).to_row()

    assert row["input_tokens"] == ""
    assert row["total_tokens"] == ""
    assert row["ai_model_id"] == "a-model"


def test_a_failed_assessment_records_why_and_claims_no_verdict() -> None:
    """The row must be able to say "a model was asked and gave us nothing"."""
    result = _result()
    result.assessment = RiskAssessment.not_assessed(
        "unreadable", model_id="a-model", error="Bedrock call failed: bad model id"
    )
    row = build_audit_event(result, settings=SETTINGS, verdict_source="offline").to_row()

    assert row["ai_category"] == "Not Assessed"
    assert "bad model id" in row["ai_error"]
    assert row["verdict_source"] == "offline"


def test_no_assessment_leaves_every_ai_cell_empty() -> None:
    """The CLI never calls Bedrock; its rows must not imply a model ran."""
    row = build_audit_event(_result(), settings=SETTINGS).to_row()

    for column in ("ai_category", "ai_model_id", "ai_confidence", "ai_error", "input_tokens"):
        assert row[column] == "", column


def test_the_source_digest_identifies_the_reviewed_bytes(tmp_path: Path) -> None:
    """The filename does not identify a document; the bytes do."""
    src = tmp_path / "vendor.txt"
    src.write_text("some vpat bytes", encoding="utf-8")
    row = build_audit_event(_result(), source_path=str(src), settings=SETTINGS).to_row()

    # sha256("some vpat bytes"), independently computed.
    import hashlib

    assert row["source_sha256"] == hashlib.sha256(b"some vpat bytes").hexdigest()
    assert row["source_bytes"] == "15"


def test_an_unreadable_source_does_not_break_the_event() -> None:
    row = build_audit_event(_result(), source_path="/nope/missing.pdf", settings=SETTINGS).to_row()

    assert row["source_sha256"] == ""
    assert row["source_bytes"] == ""
    assert row["product_name"] == "TestProduct"  # the rest of the row survives


def test_unresolved_criteria_are_counted() -> None:
    """The corpus scoreboard's `unres` column, per run: the parser-went-blank signal."""
    result = _result()
    result.document.criteria.append(VPATCriterion("2.1.1", "Keyboard", "AA", "", ""))
    row = build_audit_event(result, settings=SETTINGS).to_row()

    assert row["criteria_total"] == "3"
    assert row["unresolved_criteria"] == "1"
