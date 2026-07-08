"""Generate a demo v10 report from ScreenSteps-like data for visual review."""
import logging
from pathlib import Path
from datetime import date
from vpat_reviewer.domain.models import VPATData, VPATCriterion
from vpat_reviewer.domain.scoring import compliance_score, get_barriers as get_aa_barriers
from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.reporting.reportlab_renderer import generate_report, validate_report

logging.basicConfig(level=logging.INFO)

def crit(cid, level, status, remarks="", section="wcag"):
    return VPATCriterion(criterion_id=cid, level=level, raw_status=status,
                         normalized_status=status, remarks=remarks, section=section)

d = VPATData(
    product_name="ScreenSteps",
    product_version="",
    vendor_name="ScreenSteps",
    vendor_report_date_raw="March 2, 2022 (vendor lists \u201cLast updated 3/2/2022\u201d)",
    vendor_report_date=date(2022, 3, 2),
    vpat_edition="VPAT\u00ae Version 2.4, WCAG Edition",
    vendor_contact="(866) 275-7856 \u00b7 support@screensteps.com",
    sfbrn_contact="accessibility@sfbrn.org \u00b7 j.hale@csueastbay.edu",
    product_description=("Knowledge base software that reduces mistakes, questions, "
        "and onboarding time. Vendor note: \u201cOnly the customer facing Knowledge "
        "Based View was VPAT assessed (not admin area).\u201d"),
    product_type="Web-based knowledge base / documentation platform (SaaS)",
    evaluation_methods=("The vendor reports that conformance was assessed using Manual "
        "Testing and the WAVE Tool (WebAIM's Web Accessibility Evaluation Tool), "
        "supplemented in individual remarks by Google Chrome's accessibility inspector."),
    standards_reviewed=["WCAG 2.0 Level A", "WCAG 2.0 Level AA",
                        "WCAG 2.1 Level A", "WCAG 2.1 Level AA"],
    is_outdated=True,
    outdated_note="Vendor report date is more than 12 months older than the review date.",
)

# Level AA — 20 WCAG 2.1 AA criteria: 13 Supports, 5 PS, 2 NA
aa_supports = ["1.2.5","1.3.4","1.3.5","1.4.3","1.4.4","1.4.5","1.4.10",
               "1.4.11","1.4.12","1.4.13","2.4.5","2.4.7","3.2.4"]
d.criteria += [crit(c, "AA", "Supports", "") for c in aa_supports]
d.criteria += [
    crit("1.2.4", "AA", "Not Applicable", "ScreenSteps does not use synchronized media."),
    crit("3.3.4", "AA", "Not Applicable", "ScreenSteps does not process financial and PII transactions."),
    crit("2.4.6", "AA", "Partially Supports",
         "Pages have descriptive headings and labels. Labels are unique contextual."),
    crit("3.1.2", "AA", "Partially Supports",
         "Article contents are NOT limited to English and can also have combination of "
         "multiple languages all together. Refers to the HTML language(lang) attribute."),
    crit("3.2.3", "AA", "Partially Supports",
         "Navigation models are consistent across pages and use headings and ARIA "
         "navigation landmarks to help orient users."),
    crit("3.3.3", "AA", "Partially Supports",
         "Error messages are communicated usign a combination of ARIA alerts, ARIA "
         "landmarks, headings and links."),
    crit("4.1.3", "AA", "Partially Supports", "Status Messages have ARIA attributes."),
]
# Level A sample rows
a_supports = ["1.2.1","1.3.1","1.3.2","1.3.3","1.4.1","1.4.2","2.1.1","2.1.2",
              "2.1.4","2.2.1","2.3.1","2.4.2","2.4.3","2.4.4","2.5.1","2.5.2",
              "2.5.3","3.1.1","3.2.1","3.2.2","3.3.1"]
d.criteria += [crit(c, "A", "Supports", "") for c in a_supports]
d.criteria += [
    crit("1.1.1","A","Partially Supports","Partial support reported by vendor."),
    crit("1.2.2","A","Not Applicable","No prerecorded media."),
    crit("1.2.3","A","Not Applicable","No prerecorded media."),
    crit("2.2.2","A","Not Applicable","No moving content."),
    crit("2.4.1","A","Partially Supports","Skip links present on most templates."),
    crit("2.5.4","A","Not Applicable","No motion actuation."),
    crit("3.3.2","A","Partially Supports","Labels present; some instructions missing."),
    crit("4.1.1","A","Partially Supports","Minor parsing issues."),
    crit("4.1.2","A","Partially Supports","Name, role, value mostly exposed."),
]

score_info = compliance_score(d)
print("Score:", score_info["score"], "| supported:", score_info["supported"],
      "| reviewable:", score_info["total"], "| NA excluded:", score_info["na_excluded"])

answers = {"audience": "campus_wide", "access_impact": "limits_some",
           "legal_exposure": "medium", "deployment": "campus_wide"}
impact = calculate_impact(answers, get_aa_barriers(d), score_info)
impact["final_level"] = impact["suggested_level"]

out = str(Path(__file__).with_name("demo_ScreenSteps_v10.pdf"))
generate_report(d, score_info, impact, answers, out, logo_path="")
ok, problems = validate_report(out)
print("Validation:", "OK" if ok else problems)
