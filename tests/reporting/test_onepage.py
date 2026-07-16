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


def _text(path: Path) -> str:
    """The page's text with wrapping flattened.

    Assertions here are about what the sheet *says*; where ReportLab happens to
    break a line is a layout detail, and a test that couples to it fails the next
    time the font or a budget changes without anything being wrong.
    """
    from pypdf import PdfReader

    return " ".join(PdfReader(str(path)).pages[0].extract_text().split())


def test_the_summary_states_the_score_and_the_barrier_count(tmp_path: Path) -> None:
    out = tmp_path / "summary.pdf"
    OnePageRenderer().render(_inputs(_doc(n_barriers=3), verdict="Deny"), str(out))

    text = _text(out)
    assert "SUMMARY" in text
    assert "3 Level AA barrier(s)" in text
    assert "25%" in text  # 1 of 4 AA criteria supported
    assert "below the SFBRN 90% threshold" in text


def test_the_summary_survives_a_clean_document(tmp_path: Path) -> None:
    """No barriers is a sentence, not an omission -- silence reads as a bug."""
    out = tmp_path / "clean.pdf"
    OnePageRenderer().render(_inputs(_doc(n_barriers=0), verdict="Good to Go"), str(out))

    assert "No Level AA barriers were identified." in _text(out)


def test_the_sheet_shows_the_impact_answers_behind_the_level(tmp_path: Path) -> None:
    """Impact outranks the score in classify_report, so its basis cannot be off-page."""
    out = tmp_path / "basis.pdf"
    OnePageRenderer().render(_inputs(_doc(), verdict="Minor Issue"), str(out))

    text = _text(out).replace("\n", " ")
    assert "Impact basis:" in text
    assert "Limits some access" in text
    assert "Medium legal exposure" in text
    assert "Department deployment" in text


def test_a_reviewer_override_is_named_as_one(tmp_path: Path) -> None:
    """An override is the reviewer's call, not the computed rating; say so."""
    inputs = _inputs(_doc(), verdict="Need TAAP")
    inputs.impact["suggested_level"] = "Low"
    inputs.impact["final_level"] = "High"
    out = tmp_path / "override.pdf"
    OnePageRenderer().render(inputs, str(out))

    text = _text(out).replace("\n", " ")
    assert "set to High by the reviewer" in text
    assert "suggested Low" in text


def test_no_override_note_when_the_reviewer_took_the_suggestion(tmp_path: Path) -> None:
    inputs = _inputs(_doc(), verdict="Minor Issue")
    inputs.impact["final_level"] = inputs.impact["suggested_level"]
    out = tmp_path / "nooverride.pdf"
    OnePageRenderer().render(inputs, str(out))

    assert "by the reviewer" not in _text(out)


def test_an_unknown_answer_is_shown_not_dropped() -> None:
    """It drove the rating either way -- hiding it leaves the level unexplained."""
    from vpat_reviewer.reporting.onepage import _ACCESS_LABEL, _answer

    assert _answer({"access_impact": "limits_some"}, "access_impact", _ACCESS_LABEL) == (
        "Limits some access"
    )
    assert _answer({"access_impact": "some_new_value"}, "access_impact", _ACCESS_LABEL) == (
        "some new value"
    )
    assert _answer({}, "access_impact", _ACCESS_LABEL) == ""


def test_renders_without_impact_answers(tmp_path: Path) -> None:
    """A caller that supplies none must not print a dangling 'Impact basis:' label."""
    doc = _doc()
    inputs = ReportInputs(
        document=doc,
        score=dict(compliance_score(doc)),
        impact={},
        answers={},
        settings=SETTINGS,
    )
    out = tmp_path / "noanswers.pdf"
    OnePageRenderer().render(inputs, str(out))

    assert _pages(out) == 1
    assert "Impact basis" not in _text(out)


def test_an_unusable_threshold_does_not_take_the_report_down() -> None:
    """settings.json is hand-edited for these keys; a typo must not crash it."""
    from vpat_reviewer.reporting.onepage import _threshold

    assert _threshold({"threshold": "85"}) == 85
    assert _threshold({}) == 90
    for bad in ({"threshold": "ninety"}, {"threshold": None}):
        assert _threshold(bad) == 90


def test_renderer_for_honors_the_setting() -> None:
    assert isinstance(renderer_for({"report_style": "one_page"}), OnePageRenderer)
    assert isinstance(renderer_for({"report_style": "full"}), ReportLabRenderer)


def test_renderer_for_falls_back_to_the_full_report() -> None:
    """A typo must not silently downgrade a reviewer to less of the review."""
    for bad in ({}, None, {"report_style": ""}, {"report_style": "nonsense"}):
        assert isinstance(renderer_for(bad), ReportLabRenderer)  # type: ignore[arg-type]
