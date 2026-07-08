"""Golden-file corpus: parse each fixture and compare to a frozen expected JSON.

This is the safety net that lets the parser be refactored with confidence — if a
change alters what any real-world-shaped VPAT parses to, a golden test fails.

Add a fixture: drop ``tests/fixtures/txt/<name>.txt``, then regenerate its golden::

    VPAT_REGEN_FIXTURES=1 python -m pytest tests/parsing/test_fixtures.py

Review the generated ``<name>.expected.json`` for correctness, then commit both.

Date-derived fields (``is_outdated``, ``outdated_note``, the parsed date object)
are intentionally excluded from the snapshot because they depend on today's date.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from vpat_reviewer.domain.models import VPATDocument
from vpat_reviewer.domain.scoring import compliance_score, get_barriers
from vpat_reviewer.parsing import parse_vpat

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "txt"
_INPUTS = sorted(_FIXTURE_DIR.glob("*.txt"))


def _normalize(doc: VPATDocument) -> dict[str, Any]:
    info = compliance_score(doc)
    return {
        "product_name": doc.product_name,
        "product_version": doc.product_version,
        "vendor_name": doc.vendor_name,
        "vendor_report_date_raw": doc.vendor_report_date_raw,
        "standards_reviewed": doc.standards_reviewed,
        "score": info["score"],
        "supported": info["supported"],
        "reviewable_total": info["total"],
        "barriers": [b.criterion_id for b in get_barriers(doc)],
        "criteria": [
            {
                "id": c.criterion_id,
                "level": c.level,
                "status": c.normalized_status,
                "section": c.section,
            }
            for c in doc.criteria
        ],
    }


@pytest.mark.parametrize("input_path", _INPUTS, ids=lambda p: p.stem)
def test_fixture_matches_golden(input_path: Path) -> None:
    doc = parse_vpat(str(input_path))
    actual = _normalize(doc)
    golden = input_path.with_suffix(".expected.json")

    if os.environ.get("VPAT_REGEN_FIXTURES"):
        golden.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pytest.skip(f"regenerated {golden.name}")

    assert golden.exists(), f"missing golden {golden.name}; run with VPAT_REGEN_FIXTURES=1"
    expected = json.loads(golden.read_text(encoding="utf-8"))
    assert actual == expected


def test_corpus_is_non_empty() -> None:
    assert _INPUTS, "no fixtures found under tests/fixtures/txt/"
