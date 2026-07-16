"""The one-pager's contract is its page count; these tests defend that."""

from __future__ import annotations

from pathlib import Path

from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.models import VPATCriterion, VPATDocument
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.domain.scoring import compliance_score, get_barriers
from vpat_reviewer.reporting import (
    OnePageRenderer,
    ReportInputs,
    ReportLabRenderer,
    ReportRenderer,
    renderer_for,
)

ANSWERS = {
    "audience": "department",
    "access_impact": "limits_some",
    "legal_exposure": "medium",
    "deployment": "department",
}
SETTINGS = {"org_short": "SFBRN", "reviewer_name": "A. Reviewer", "report_style": "one_page"}


def _doc(n_barriers: int = 3, title: str = "Contrast (Minimum)") -> VPATDocument:
    d = VPATDocument(product_name="TestProduct", vendor_name="Vendor Inc", product_version="1.0")
    d.criteria = [
        VPATCriterion("1.1.1", "Non-text Content", "AA", "Supports", normalize_status("Supports"))
    ]
    for i in range(n_barriers):
        d.criteria.append(
            VPATCriterion(
                f"1.4.{i + 1}",
                title,
                "AA",
                "Does Not Support",
                normalize_status("Does Not Support"),
            )
        )
    return d


def _inputs(doc: VPATDocument, **kw: object) -> ReportInputs:
    score = compliance_score(doc)
    impact = calculate_impact(ANSWERS, get_barriers(doc), score)
    return ReportInputs(
        document=doc,
        score=dict(score),
        impact=dict(impact),
        answers=ANSWERS,
        settings=SETTINGS,
        **kw,  # type: ignore[arg-type]
    )


def _pages(path: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(path)).pages)


def test_satisfies_the_port() -> None:
    assert isinstance(OnePageRenderer(), ReportRenderer)
    assert OnePageRenderer().output_suffix == ".pdf"


def test_renders_a_single_page(tmp_path: Path) -> None:
    out = tmp_path / "one.pdf"
    OnePageRenderer().render(_inputs(_doc(), verdict="Minor Issue"), str(out))

    assert out.exists()
    with out.open("rb") as f:
        assert f.read(5) == b"%PDF-"
    assert _pages(out) == 1


def test_stays_one_page_when_content_explodes(tmp_path: Path) -> None:
    """The trim levels exist for this: a real VPAT can be far bigger than the page.

    Without progressive trimming this silently becomes a two-page 'one-pager',
    which is the one thing the client asked us not to ship.
    """
    doc = _doc(n_barriers=40, title="An extremely long criterion title " * 6)
    inputs = _inputs(
        doc,
        verdict="Deny",
        recommendation="Remediate everything. " * 200,
    )
    inputs.impact["rationale"] = ["A very long rationale sentence. " * 100]
    out = tmp_path / "big.pdf"
    OnePageRenderer().render(inputs, str(out))

    assert _pages(out) == 1


def test_validate_accepts_its_own_output(tmp_path: Path) -> None:
    out = tmp_path / "v.pdf"
    r = OnePageRenderer()
    r.render(_inputs(_doc(), verdict="Good to Go"), str(out))

    ok, problems = r.validate(str(out))
    assert ok, f"validation failed: {problems}"


def test_validate_rejects_a_multi_page_pdf(tmp_path: Path) -> None:
    """validate() must actually check the page count, not just the PDF header."""
    out = tmp_path / "full.pdf"
    ReportLabRenderer().render(_inputs(_doc(), verdict="Minor Issue"), str(out))

    ok, problems = OnePageRenderer().validate(str(out))
    assert not ok
    assert any("page" in p.lower() for p in problems)


def test_renders_without_a_verdict(tmp_path: Path) -> None:
    """The CLI supplies no verdict; that must not crash the sheet."""
    out = tmp_path / "noverdict.pdf"
    OnePageRenderer().render(_inputs(_doc()), str(out))

    assert _pages(out) == 1


def test_renders_vendor_text_containing_html_tags(tmp_path: Path) -> None:
    """Same ReportLab markup trap as the full renderer -- see test_reportlab_renderer."""
    doc = _doc(title="Uses <a> anchors & <b> bold")
    doc.product_name = "Tag <b>Co</b> & Sons"
    out = tmp_path / "tags.pdf"
    OnePageRenderer().render(_inputs(doc, verdict="Need TAAP"), str(out))

    assert _pages(out) == 1


def test_renderer_for_honors_the_setting() -> None:
    assert isinstance(renderer_for({"report_style": "one_page"}), OnePageRenderer)
    assert isinstance(renderer_for({"report_style": "full"}), ReportLabRenderer)


def test_renderer_for_falls_back_to_the_full_report() -> None:
    """A typo must not silently downgrade a reviewer to less of the review."""
    for bad in ({}, None, {"report_style": ""}, {"report_style": "nonsense"}):
        assert isinstance(renderer_for(bad), ReportLabRenderer)  # type: ignore[arg-type]
