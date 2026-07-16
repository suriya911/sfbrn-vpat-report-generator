"""Document-type classification.

The cases here are modelled on the real files in docs/completed_forms: reviewers
are sent remediation plans, bespoke audit reports, blank templates and review
rubrics alongside actual VPATs, and several of those quote WCAG criteria.
"""

from __future__ import annotations

from vpat_reviewer.domain.models import DocumentKind, VPATCriterion
from vpat_reviewer.parsing.doctype import classify_document


def _criteria(n: int, *, answered: bool = True) -> list[VPATCriterion]:
    out = []
    for i in range(n):
        status = "Supports" if answered else ""
        out.append(
            VPATCriterion(
                criterion_id=f"1.1.{i}",
                level="A",
                raw_status=status,
                normalized_status=status or "Not Evaluated",
            )
        )
    return out


def test_real_vpat_is_recognised():
    text = (
        "Voluntary Product Accessibility Template\n"
        "Criteria Conformance Level Remarks and Explanations"
    )
    verdict = classify_document(text, _criteria(50))
    assert verdict.kind is DocumentKind.VPAT
    assert verdict.reasons


def test_short_in_house_acr_is_accepted():
    """A brief report that names its standard and answers criteria is still a VPAT.

    Rejecting on criterion count alone would fail real, abbreviated reports --
    and a false "not a VPAT" blocks work, whereas UNKNOWN merely proceeds.
    """
    text = "Applicable Standards: WCAG 2.1 Level AA, Section 508 (Revised 2017)"
    verdict = classify_document(text, _criteria(4))
    assert verdict.kind is DocumentKind.VPAT


def test_taap_remediation_plan_is_rejected():
    """Anatomy LT: a Temporary Alternative Access Plan, not a vendor claim."""
    text = "Temporary Alternative Access Plan (TAAP)\nKnown Accessibility Barriers\nSection 508"
    verdict = classify_document(text, [])
    assert verdict.kind is DocumentKind.NOT_A_VPAT
    assert "Temporary Alternative Access Plan" in verdict.reasons[0]


def test_review_guide_is_rejected_despite_quoting_criteria():
    """The review rubric quotes dozens of criteria but is not a VPAT.

    This is why criterion count alone cannot decide the question.
    """
    text = "VPAT-ACR Review In Depth Guide\nWCAG Word Substitutions\nWCAG Exceptions"
    verdict = classify_document(text, _criteria(38))
    assert verdict.kind is DocumentKind.NOT_A_VPAT


def test_risk_scoring_worksheet_is_rejected():
    verdict = classify_document("ICT Risk Scoring\nRisk Level Definitions", [])
    assert verdict.kind is DocumentKind.NOT_A_VPAT


def test_custom_audit_report_with_no_criteria_is_rejected():
    """Appsian: a bespoke test report using Pass/Fail, with no WCAG ids."""
    text = "Accessibility Report\nEvaluation Focus | Findings | Result\nFail - Minor"
    verdict = classify_document(text, [])
    assert verdict.kind is DocumentKind.NOT_A_VPAT
    assert "no WCAG success criteria" in verdict.reasons[0]


def test_blank_template_is_distinguished_from_a_filled_one():
    """The TAAP/VPAT templates list every criterion and answer none."""
    text = "Voluntary Product Accessibility Template\nConformance Level\nRemarks and Explanations"
    verdict = classify_document(text, _criteria(50, answered=False))
    assert verdict.kind is DocumentKind.BLANK_TEMPLATE
    assert "unfilled template" in verdict.reasons[0]


def test_incidental_criterion_mentions_are_not_claimed_as_a_vpat():
    """Prose citing a couple of criteria earns no verdict either way."""
    verdict = classify_document("A blog post mentioning 1.1.1 and 1.4.3 in passing.", _criteria(2))
    assert verdict.kind is DocumentKind.UNKNOWN


def test_unnamed_but_substantial_table_is_accepted():
    """Some vendors ship the table without ever writing the word "VPAT"."""
    verdict = classify_document("Criteria Conformance Level Remarks", _criteria(50))
    assert verdict.kind is DocumentKind.VPAT
