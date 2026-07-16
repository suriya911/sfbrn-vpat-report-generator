"""The machine-readable record.

This is the app's contract with anything downstream -- the CLI's ``--json``, the
sidecar beside a report, and whatever later interprets a vendor's claims. It had
no tests at all until July 2026, which is how ``service.review`` came to write a
sidecar the CLI never asked for while the CLI emitted a different shape entirely.
"""

from __future__ import annotations

import json
from pathlib import Path

from vpat_reviewer import service
from vpat_reviewer.domain.policy import GradingPolicy

FIXTURE = Path(__file__).parent / "fixtures" / "txt" / "acme_basic.txt"

_SETTINGS = {
    "org_name": "Test Org",
    "org_short": "TST",
    "reviewer_name": "Reviewer",
    "reviewer_title": "Title",
    "org_contact": "",
    "threshold": 90,
    "report_title": "VPAT Report",
}


def _record() -> dict:
    result = service.analyze(str(FIXTURE), policy=GradingPolicy.default())
    return service.to_dict(result)


def test_record_carries_identity_and_score():
    rec = _record()
    assert rec["product_name"] == "Acme Learn"
    assert rec["vendor_name"] == "Acme Corporation"
    assert rec["score"] == 33
    assert rec["barriers"] == ["1.4.3", "2.4.7"]
    assert rec["document_kind"] == "vpat"


def test_record_keeps_the_vendors_own_words_beside_our_reading():
    """Normalization is lossy and sometimes wrong, so the evidence must survive.

    A consumer that disagrees with our canonical status needs to see what the
    vendor actually wrote.
    """
    rec = _record()
    by_id = {c["id"]: c for c in rec["criteria"]}
    assert by_id["1.4.3"]["raw_status"] == "Partially Supports"
    assert by_id["1.4.3"]["status"] == "Partially Supports"
    assert by_id["1.4.3"]["title"] == "Contrast (Minimum)"
    assert "low-contrast" in by_id["1.4.3"]["remarks"]


def test_record_states_what_kind_of_document_this_was():
    """A consumer must be able to refuse a score computed from a non-VPAT."""
    rec = _record()
    assert rec["document_kind"] == "vpat"
    assert rec["document_kind_reasons"]


def test_record_is_json_serializable():
    json.dumps(_record())


def test_review_writes_the_sidecar_next_to_the_report(tmp_path: Path):
    out = tmp_path / "report.pdf"
    result = service.review(
        str(FIXTURE), str(out), policy=GradingPolicy.default(), settings=_SETTINGS
    )
    sidecar = tmp_path / "report.json"
    assert sidecar.exists()
    assert result.json_path == str(sidecar)
    assert json.loads(sidecar.read_text(encoding="utf-8"))["product_name"] == "Acme Learn"


def test_write_json_records_its_path(tmp_path: Path):
    result = service.analyze(str(FIXTURE), policy=GradingPolicy.default())
    out = tmp_path / "record.json"
    assert service.write_json(result, str(out)) == str(out)
    assert result.json_path == str(out)
    assert json.loads(out.read_text(encoding="utf-8"))["criteria"]
