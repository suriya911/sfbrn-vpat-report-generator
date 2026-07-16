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


def test_renders_vendor_text_containing_html_tags(tmp_path: Path):
    """Vendor prose that names HTML tags must not be parsed as markup.

    ReportLab reads Paragraph text as mini-HTML. H5P's real VPAT says a progress
    bar has "clickable elements implemented as <a> tags"; that <a> was read as an
    unclosed anchor and killed the whole report with
    "Parse error: saw </para> instead of expected </a>".
    """
    d = VPATDocument(
        product_name="Tag <b>Bold</b> & Co",
        vendor_name="Vendor <script>alert(1)</script>",
        product_description="A tool using <a> anchors & <em> emphasis",
    )
    d.criteria = [
        VPATCriterion(
            "2.4.4",
            "Link Purpose (In Context)",
            "A",
            "Partially Supports",
            normalize_status("Partially Supports"),
            remarks=(
                "Example: In Course Presentation the progress bar has clickable "
                "elements implemented as <a> tags. They have long hidden texts "
                "for screen readers as well as shorter textual versions "
                "implemented as tool tips."
            ),
        ),
    ]
    score = compliance_score(d)
    answers = {
        "audience": "department",
        "access_impact": "limits_some",
        "legal_exposure": "medium",
        "deployment": "department",
    }
    impact = calculate_impact(answers, get_barriers(d), score)
    # AI-generated rationale is free text too, so it gets the same treatment.
    impact = dict(impact)
    impact["rationale"] = [*impact.get("rationale", []), "Model flagged <a> and <img> usage"]
    inputs = ReportInputs(document=d, score=dict(score), impact=impact, answers=answers)

    out = tmp_path / "tags.pdf"
    ReportLabRenderer().render(inputs, str(out))

    assert out.exists() and out.stat().st_size > 0
    with out.open("rb") as f:
        assert f.read(5) == b"%PDF-"
