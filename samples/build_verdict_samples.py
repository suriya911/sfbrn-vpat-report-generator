"""Build the five per-verdict sample VPATs and verify each lands in its bucket.

Run from the project root:  python samples/build_verdict_samples.py

Writes samples/verdict_cases/<case>.txt and <case>.expected.json, then prints a
pass/fail line per case asserting the end-to-end verdict still matches its target.
"""

from __future__ import annotations

import json
from pathlib import Path

from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.scoring import get_barriers
from vpat_reviewer.domain.verdict import classify_report
from vpat_reviewer.service import analyze, to_dict

OUT = Path(__file__).resolve().parent / "verdict_cases"

# Real WCAG titles so the docs read like genuine ACRs.
AA = {
    "1.2.4": "Captions (Live)",
    "1.2.5": "Audio Description (Prerecorded)",
    "1.3.4": "Orientation",
    "1.3.5": "Identify Input Purpose",
    "1.4.3": "Contrast (Minimum)",
    "1.4.4": "Resize Text",
    "1.4.5": "Images of Text",
    "1.4.10": "Reflow",
    "1.4.11": "Non-text Contrast",
    "1.4.12": "Text Spacing",
    "1.4.13": "Content on Hover or Focus",
    "2.4.5": "Multiple Ways",
    "2.4.6": "Headings and Labels",
    "2.4.7": "Focus Visible",
    "2.4.11": "Focus Not Obscured (Minimum)",
    "2.5.7": "Dragging Movements",
    "2.5.8": "Target Size (Minimum)",
    "3.1.2": "Language of Parts",
    "3.2.3": "Consistent Navigation",
    "3.2.4": "Consistent Identification",
    "3.3.3": "Error Suggestion",
    "3.3.4": "Error Prevention (Legal, Financial, Data)",
    "4.1.3": "Status Messages",
}
A = {
    "1.1.1": "Non-text Content",
    "1.3.1": "Info and Relationships",
    "2.1.1": "Keyboard",
    "2.4.3": "Focus Order",
    "4.1.2": "Name, Role, Value",
}
AA_IDS = list(AA)

REMARKS = {
    "Supports": "Meets the success criterion across the product.",
    "Partially Supports": "Meets the criterion in most areas; some components fall short.",
    "Does Not Support": "The product does not currently meet this criterion.",
}


def _block(cid: str, title: str, level: str, status: str) -> str:
    return f"{cid} {title} (Level {level})\n{status}\nRemarks:\n{REMARKS.get(status, '')}\n"


def _make_doc(product, version, vendor, rdate, a_status, aa_statuses) -> str:
    lines = [
        f"Name of Product/Version: {product} {version}",
        f"Report Date: {rdate}",
        f"Vendor: {vendor}",
        "Applicable Standards: WCAG 2.1 Level AA, Section 508 (Revised 2017)",
        "",
    ]
    for cid, st in zip(A, a_status, strict=False):
        lines.append(_block(cid, A[cid], "A", st))
    for cid, st in aa_statuses:
        lines.append(_block(cid, AA[cid], "AA", st))
    return "\n".join(lines)


def _aa_mix(n_support, n_partial, n_deny):
    ids = AA_IDS[: n_support + n_partial + n_deny]
    out, i = [], 0
    for _ in range(n_support):
        out.append((ids[i], "Supports"))
        i += 1
    for _ in range(n_partial):
        out.append((ids[i], "Partially Supports"))
        i += 1
    for _ in range(n_deny):
        out.append((ids[i], "Does Not Support"))
        i += 1
    return out


# (filename, product, version, vendor, date, A-statuses, AA mix, recommended answers, target)
CASES = [
    (
        "good_to_go",
        "Northstar Docs",
        "3.0",
        "Northstar Software",
        "May 2025",
        ["Supports"] * 5,
        _aa_mix(10, 0, 0),
        {
            "audience": "small_team",
            "access_impact": "no_limit",
            "legal_exposure": "low",
            "deployment": "individual",
        },
        "Good to Go",
    ),
    (
        "minor_issue",
        "BrightForms",
        "2.4",
        "BrightForms Inc.",
        "April 2025",
        ["Supports"] * 5,
        _aa_mix(8, 2, 0),
        {
            "audience": "small_team",
            "access_impact": "limits_some",
            "legal_exposure": "low",
            "deployment": "department",
        },
        "Minor Issue",
    ),
    (
        "needs_manual_review",
        "Cascade Analytics",
        "7.1",
        "Cascade Data Co.",
        "March 2025",
        ["Supports"] * 4 + ["Partially Supports"],
        _aa_mix(6, 4, 0),
        {
            "audience": "small_team",
            "access_impact": "limits_some",
            "legal_exposure": "low",
            "deployment": "department",
        },
        "Needs Manual Review",
    ),
    (
        "need_taap",
        "Adobe Audience Manager",
        "24.9",
        "Adobe",
        "September 2024",
        ["Supports"] * 4 + ["Partially Supports"],
        _aa_mix(13, 4, 3),
        {
            "audience": "campus_wide",
            "access_impact": "limits_some",
            "legal_exposure": "high",
            "deployment": "campus_wide",
        },
        "Need TAAP",
    ),
    (
        "deny",
        "LegacyPortal Suite",
        "1.0",
        "OldStack Systems",
        "January 2025",
        ["Partially Supports"] * 3 + ["Does Not Support"] * 2,
        _aa_mix(6, 3, 11),
        {
            "audience": "campus_wide",
            "access_impact": "denies_access",
            "legal_exposure": "high",
            "deployment": "campus_wide",
        },
        "Deny",
    ),
]


def main(good_cut: int = 90) -> bool:
    OUT.mkdir(parents=True, exist_ok=True)
    all_ok = True
    for fname, product, ver, vendor, rdate, a_st, aa, answers, target in CASES:
        (OUT / f"{fname}.txt").write_text(
            _make_doc(product, ver, vendor, rdate, a_st, aa), encoding="utf-8"
        )

        result = analyze(str(OUT / f"{fname}.txt"))
        score = result.score.get("score")
        barriers = get_barriers(result.document)
        impact = calculate_impact(answers, barriers, result.score)
        verdict = classify_report(
            score, impact["suggested_level"], len(barriers), answers["access_impact"], good_cut
        )

        ok = verdict == target
        all_ok &= ok
        print(
            f"{'OK ' if ok else 'XX '} {fname:22} score={str(score):>4} "
            f"barriers={len(barriers):>2} impact={impact['suggested_level']:>6} "
            f"-> {verdict}  (target {target})"
        )

        payload = to_dict(result)
        payload["recommended_answers"] = answers
        payload["expected_verdict"] = target
        (OUT / f"{fname}.expected.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print("\nALL OK" if all_ok else "\nSOME FAILED")
    return all_ok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
