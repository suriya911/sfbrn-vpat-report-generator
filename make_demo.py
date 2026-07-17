"""Generate a demo report from ScreenSteps-like data for visual review.

Running this module builds a representative VPAT in memory, renders it to a PDF
next to this file, and prints the compliance score plus a validation check. It
doubles as the project's behavior anchor: the score must stay ``77`` and
validation must pass (see CLAUDE.md).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.models import VPATCriterion, VPATData
from vpat_reviewer.domain.scoring import compliance_score, get_barriers
from vpat_reviewer.reporting.reportlab_renderer import generate_report, validate_report


def crit(
    cid: str, level: str, status: str, remarks: str = "", section: str = "wcag"
) -> VPATCriterion:
    """Build one demo criterion (the statuses used here are already canonical)."""
    return VPATCriterion(
        criterion_id=cid,
        level=level,
        raw_status=status,
        normalized_status=status,
        remarks=remarks,
        section=section,
    )


def build_demo_document() -> VPATData:
    """Assemble a representative ScreenSteps-like VPAT.

    Grading is cumulative (Levels A and AA together). Level AA holds
    13 Supports, 5 Partially Supports, and 2 Not Applicable; Level A holds
    21 Supports, 5 Partially Supports, and 4 Not Applicable. Combined:
    34 supported of 44 reviewable (6 NA excluded) → the anchor score of 77.
    Keep those counts in sync with the rows below if you edit them.
    """
    doc = VPATData(
        product_name="ScreenSteps",
        product_version="",
        vendor_name="ScreenSteps",
        vendor_report_date_raw='March 2, 2022 (vendor lists "Last updated 3/2/2022")',
        vendor_report_date=date(2022, 3, 2),
        vpat_edition="VPAT® Version 2.4, WCAG Edition",
        vendor_contact="(866) 275-7856 · support@screensteps.com",
        sfbrn_contact="accessibility@sfbrn.org · j.hale@csueastbay.edu",
        product_description=(
            "Knowledge base software that reduces mistakes, questions, and "
            'onboarding time. Vendor note: "Only the customer facing Knowledge '
            'Based View was VPAT assessed (not admin area)."'
        ),
        product_type="Web-based knowledge base / documentation platform (SaaS)",
        evaluation_methods=(
            "The vendor reports that conformance was assessed using Manual Testing "
            "and the WAVE Tool (WebAIM's Web Accessibility Evaluation Tool), "
            "supplemented in individual remarks by Google Chrome's accessibility "
            "inspector."
        ),
        standards_reviewed=[
            "WCAG 2.0 Level A",
            "WCAG 2.0 Level AA",
            "WCAG 2.1 Level A",
            "WCAG 2.1 Level AA",
        ],
        is_outdated=True,
        outdated_note="Vendor report date is more than 12 months older than the review date.",
    )

    # Level AA — 13 Supports.
    aa_supports = (
        "1.2.5 1.3.4 1.3.5 1.4.3 1.4.4 1.4.5 1.4.10 1.4.11 1.4.12 1.4.13 2.4.5 2.4.7 3.2.4"
    )
    doc.criteria += [crit(c, "AA", "Supports") for c in aa_supports.split()]
    # Level AA — 2 Not Applicable + 5 Partially Supports.
    doc.criteria += [
        crit("1.2.4", "AA", "Not Applicable", "ScreenSteps does not use synchronized media."),
        crit(
            "3.3.4",
            "AA",
            "Not Applicable",
            "ScreenSteps does not process financial and PII transactions.",
        ),
        crit(
            "2.4.6",
            "AA",
            "Partially Supports",
            "Pages have descriptive headings and labels. Labels are unique contextual.",
        ),
        crit(
            "3.1.2",
            "AA",
            "Partially Supports",
            "Article contents are NOT limited to English and can also have combination of "
            "multiple languages all together. Refers to the HTML language(lang) attribute.",
        ),
        crit(
            "3.2.3",
            "AA",
            "Partially Supports",
            "Navigation models are consistent across pages and use headings and ARIA "
            "navigation landmarks to help orient users.",
        ),
        crit(
            "3.3.3",
            "AA",
            "Partially Supports",
            "Error messages are communicated usign a combination of ARIA alerts, ARIA "
            "landmarks, headings and links.",
        ),
        crit("4.1.3", "AA", "Partially Supports", "Status Messages have ARIA attributes."),
    ]

    # Level A rows — graded alongside AA (cumulative conformance target).
    a_supports = (
        "1.2.1 1.3.1 1.3.2 1.3.3 1.4.1 1.4.2 2.1.1 2.1.2 2.1.4 2.2.1 2.3.1 "
        "2.4.2 2.4.3 2.4.4 2.5.1 2.5.2 2.5.3 3.1.1 3.2.1 3.2.2 3.3.1"
    )
    doc.criteria += [crit(c, "A", "Supports") for c in a_supports.split()]
    doc.criteria += [
        crit("1.1.1", "A", "Partially Supports", "Partial support reported by vendor."),
        crit("1.2.2", "A", "Not Applicable", "No prerecorded media."),
        crit("1.2.3", "A", "Not Applicable", "No prerecorded media."),
        crit("2.2.2", "A", "Not Applicable", "No moving content."),
        crit("2.4.1", "A", "Partially Supports", "Skip links present on most templates."),
        crit("2.5.4", "A", "Not Applicable", "No motion actuation."),
        crit("3.3.2", "A", "Partially Supports", "Labels present; some instructions missing."),
        crit("4.1.1", "A", "Partially Supports", "Minor parsing issues."),
        crit("4.1.2", "A", "Partially Supports", "Name, role, value mostly exposed."),
    ]
    return doc


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    doc = build_demo_document()

    score_info = compliance_score(doc)
    print(
        f"Score: {score_info['score']} | supported: {score_info['supported']} "
        f"| reviewable: {score_info['total']} | NA excluded: {score_info['na_excluded']}"
    )

    answers = {
        "audience": "campus_wide",
        "access_impact": "limits_some",
        "legal_exposure": "medium",
        "deployment": "campus_wide",
    }
    impact = calculate_impact(answers, get_barriers(doc), score_info)
    impact["final_level"] = impact["suggested_level"]  # mirror the GUI's final choice

    out = str(Path(__file__).with_name("demo_ScreenSteps.pdf"))
    generate_report(doc, score_info, impact, answers, out, logo_path="")
    ok, problems = validate_report(out)
    print("Validation:", "OK" if ok else problems)


if __name__ == "__main__":
    main()
