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


def test_analyze_scores_fixture():
    r = service.analyze(str(FIXTURE), policy=GradingPolicy.default())
    assert r.document.product_name == "Acme Learn"
    assert r.score["score"] == 50
    assert {b.criterion_id for b in r.barriers} == {"1.4.3", "2.4.7"}
    assert r.has_criteria


def test_analyze_with_answers_raises_impact():
    answers = {"access_impact": "denies_access", "legal_exposure": "high"}
    r = service.analyze(str(FIXTURE), policy=GradingPolicy.default(), answers=answers)
    assert r.impact["suggested_level"] == "High"


def test_review_produces_valid_pdf(tmp_path: Path):
    out = tmp_path / "report.pdf"
    r = service.review(str(FIXTURE), str(out), policy=GradingPolicy.default(), settings=_SETTINGS)
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"
    assert r.output_path == str(out)


def test_render_result_reuses_analysis(tmp_path: Path):
    r = service.analyze(str(FIXTURE), policy=GradingPolicy.default())
    out = tmp_path / "r2.pdf"
    service.render_result(r, str(out), settings=_SETTINGS)
    assert out.exists() and out.read_bytes()[:5] == b"%PDF-"


def test_analyze_unsupported_file():
    r = service.analyze("mystery.xlsx", policy=GradingPolicy.default())
    assert not r.has_criteria
    assert any("Unsupported" in w for w in r.warnings)
