from pathlib import Path

from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.models import VPATCriterion, VPATDocument
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.domain.scoring import compliance_score, get_barriers
from vpat_reviewer.reporting import ReportInputs, ReportLabRenderer


def _doc() -> VPATDocument:
    d = VPATDocument(product_name="RenderTest", vendor_name="Vendor Inc")
    d.criteria = [
        VPATCriterion(
            "1.4.3", "Contrast (Minimum)", "AA", "Supports", normalize_status("Supports")
        ),
        VPATCriterion(
            "2.4.7",
            "Focus Visible",
            "AA",
            "Partially Supports",
            normalize_status("Partially Supports"),
        ),
    ]
    return d


def test_output_suffix():
    assert ReportLabRenderer().output_suffix == ".pdf"


def test_renderer_produces_valid_pdf(tmp_path: Path):
    d = _doc()
    score = compliance_score(d)
    answers = {
        "audience": "department",
        "access_impact": "limits_some",
        "legal_exposure": "medium",
        "deployment": "department",
    }
    impact = calculate_impact(answers, get_barriers(d), score)
    inputs = ReportInputs(document=d, score=dict(score), impact=dict(impact), answers=answers)

    out = tmp_path / "report.pdf"
    renderer = ReportLabRenderer()
    renderer.render(inputs, str(out))

    assert out.exists() and out.stat().st_size > 0
    with out.open("rb") as f:
        assert f.read(5) == b"%PDF-"

    ok, problems = renderer.validate(str(out))
    assert ok, f"validation failed: {problems}"


def test_renderer_satisfies_protocol():
    from vpat_reviewer.reporting import ReportRenderer

    assert isinstance(ReportLabRenderer(), ReportRenderer)
