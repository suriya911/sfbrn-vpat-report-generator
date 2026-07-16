"""Decide whether a document is actually a vendor's VPAT.

Reviewers receive plenty of accessibility paperwork that is not a conformance
report: remediation plans (TAAP forms), bespoke audit reports, blank templates,
and the review guides describing how to read a VPAT in the first place. Several
of those mention WCAG criteria in passing, so "it contains criterion ids" is not
enough to identify one.

Scoring a non-VPAT is worse than refusing it: the pipeline produces a percentage
and a barrier list that look authoritative and mean nothing. So classify first,
and let the caller decline.

This lives in ``parsing/`` alongside the other heuristics that read raw text
(``metadata``, ``standards``). It is pure, and it sits at the ``parse_document``
seam the fixture corpus already tests.
"""

from __future__ import annotations

import re

from vpat_reviewer.domain.models import DocTypeVerdict, DocumentKind, VPATCriterion

# Naming the artefact is the strongest single signal a VPAT can give.
_VPAT_MARKERS = (
    r"Voluntary\s+Product\s+Accessibility\s+Template",
    r"\bVPAT\b",
    r"Accessibility\s+Conformance\s+Report",
)

# The ITI template's column headers. Present in essentially every real VPAT and
# rare anywhere else.
_ITI_HEADERS = (
    r"Conformance\s+Level",
    r"Remarks\s+and\s+Explanations",
)

# Documents that are emphatically something else. Each is a real file type SFBRN
# reviewers handle.
_NOT_VPAT_MARKERS: tuple[tuple[str, str], ...] = (
    (
        r"Temporary\s+Alternative\s+Access\s+Plan|\bTAAP\b",
        "reads as a Temporary Alternative Access Plan (a remediation plan, not a vendor claim)",
    ),
    (
        r"WCAG\s+Word\s+Substitutions|VPAT[\s-]*ACR\s+Review",
        "reads as a VPAT review guide or rubric rather than a VPAT",
    ),
    (
        r"Risk\s+Scoring|Risk\s+Level\s+Definitions",
        "reads as a procurement risk-scoring worksheet",
    ),
)

# Declaring the standard under review is a weak signal on its own, but a strong
# one next to answered criteria.
_STANDARD_DECLARED = (r"WCAG\s*2\.\d", r"Section\s+508", r"EN\s*301\s*549")

# Enough distinct real criteria that the document is plainly answering WCAG.
_STRONG_CRITERIA_COUNT = 20
# A template is recognisable by having the rows but none of the answers.
_BLANK_ANSWER_RATIO = 0.9


def _search(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_document(text: str, criteria: list[VPATCriterion]) -> DocTypeVerdict:
    """Judge what this document is, given its text and whatever parsed out of it.

    Classification runs *after* criterion parsing because the most reliable
    evidence is the parse itself: a real VPAT yields a lot of criteria with
    answers, a template yields the same criteria with none, and everything else
    yields few or no criteria at all.
    """
    reasons: list[str] = []
    wcag = [c for c in criteria if c.section == "wcag"]
    answered = [c for c in wcag if c.raw_status.strip()]

    # An explicit "this is a different document" marker outranks everything: the
    # review guide quotes dozens of criteria, and the TAAP form cites Section 508.
    for pattern, reason in _NOT_VPAT_MARKERS:
        if re.search(pattern, text, re.IGNORECASE):
            return DocTypeVerdict(DocumentKind.NOT_A_VPAT, (reason,))

    named = _search(_VPAT_MARKERS, text)
    has_headers = _search(_ITI_HEADERS, text)
    declares_standard = _search(_STANDARD_DECLARED, text)

    if not wcag:
        why = "no WCAG success criteria were found"
        if named:
            why += ", although the document mentions VPAT/ACR"
        return DocTypeVerdict(DocumentKind.NOT_A_VPAT, (why,))

    # Rows but no answers: a blank or near-blank template.
    if len(answered) / len(wcag) < (1 - _BLANK_ANSWER_RATIO):
        return DocTypeVerdict(
            DocumentKind.BLANK_TEMPLATE,
            (
                f"{len(wcag)} criteria are listed but only {len(answered)} carry a "
                f"conformance value, so this looks like an unfilled template",
            ),
        )

    # Positive evidence. Any one of these is enough: vendors are inconsistent
    # about naming the artefact, and a short in-house ACR is still an ACR. The
    # documents that are genuinely something else are caught by the markers
    # above or by having no criteria at all, so this stays deliberately generous
    # -- a false "not a VPAT" blocks real work, while an UNKNOWN merely proceeds
    # without a claim.
    if named:
        reasons.append("identifies itself as a VPAT/ACR")
    if has_headers:
        reasons.append("uses the standard VPAT table headers")
    if len(wcag) >= _STRONG_CRITERIA_COUNT:
        reasons.append(f"answers {len(answered)} of {len(wcag)} WCAG criteria")
    elif declares_standard and answered:
        reasons.append(f"declares the standard under review and answers {len(answered)} criteria")

    if reasons:
        return DocTypeVerdict(DocumentKind.VPAT, tuple(reasons))

    return DocTypeVerdict(
        DocumentKind.UNKNOWN,
        (
            f"{len(wcag)} WCAG criteria were found, but the document does not name "
            f"itself a VPAT, use the standard table headers, or state which "
            f"standard it reviews",
        ),
    )
