"""Cover-page metadata extraction. Relocated verbatim from the v10 parser.

Every ``v9 FIX`` comment marks a behavior pinned by a regression test — do not
loosen these regexes without adding a fixture that proves the new behavior.
"""

from __future__ import annotations

import re

from vpat_reviewer.parsing.text_cleanup import clean_extracted_text, is_blank_or_garbage

# Known company names — product-specific only, excludes browser/tool names.
KNOWN_VENDORS = [
    "Atlassian",
    "Microsoft",
    "Instructure",
    "Blackboard",
    "Anthology",
    "Adobe",
    "Salesforce",
    "Respondus",
    "D2L",
    "Brightspace",
    "Moodle",
    "Kaltura",
    "Panopto",
    "Echo360",
    "Turnitin",
    "ProctorU",
    "Honorlock",
    "McGraw-Hill",
    "Pearson",
    "Cengage",
    "VitalSource",
    "Chegg",
    "LinkedIn",
    "Slack",
    "Trello",
]


def extract_meta(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}

    # Product name / version
    for pat in [
        r"Name\s+of\s+Product[/\\]?Version\s*:\s*(.+)",
        r"Product\s+Name\s*:\s*(.+)",
        r"Product\s*[:/]\s*(.+)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().split("\n")[0].strip()
            # Try version with v/Version prefix first (e.g. "App v2.0" / "App Version 2.0").
            vm = re.search(r"[\s,;]+[Vv](?:ersion)?\s*([\d.]+)", raw)
            if vm:
                meta["product_name"] = _clean_product_name(raw[: vm.start()].strip())
                meta["product_version"] = vm.group(1)
            else:
                # Bare decimal version at end (e.g. "TestApp 1.0"). Requires a decimal
                # point to avoid splitting "Windows 10" -> ["Windows", "10"].
                vm2 = re.search(r"[\s]+([\d]+\.[\d]+(?:\.[\d]+)*)\s*$", raw)
                if vm2:
                    meta["product_name"] = _clean_product_name(raw[: vm2.start()].strip())
                    meta["product_version"] = vm2.group(1)
                else:
                    meta["product_name"] = _clean_product_name(raw)
            break

    # Report date — handle ordinal suffixes and simple "Date:" label.
    for pat in [
        r"Report\s+Date\s*:\s*(.+)",
        r"Date\s+of\s+Report\s*:\s*(.+)",
        r"Evaluation\s+Date\s*:\s*(.+)",
        r"^Date\s*:\s*(.+)",  # v9 FIX C: bare "Date:" label (no "Report")
        r"(?:(?!Report\s|Evaluation\s)\b)Date\s*:\s*(.+)",  # "Date:" not preceded by a word
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw_date = m.group(1).strip().split("\n")[0].strip()
            if not is_blank_or_garbage(raw_date):
                meta["vendor_report_date_raw"] = raw_date
                break

    # Vendor — explicit field.
    for pat in [
        r"(?:Company|Vendor|Manufacturer)\s*(?:Name)?\s*:\s*(.+)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            v = m.group(1).strip().split("\n")[0].strip()
            if v and len(v) < 80 and not is_blank_or_garbage(v):
                meta["vendor_name"] = v
                break

    # Vendor — scan HEADER region (first 20%) for known company names only.
    if not meta.get("vendor_name"):
        header = text[: max(int(len(text) * 0.20), 800)]
        # Pick the EARLIEST-occurring known vendor, not the first in list order —
        # otherwise a product whose description mentions another vendor (e.g.
        # "works inside Microsoft Office") is misattributed. The vendor's own name
        # appears in the cover/header before any such incidental mention.
        best_pos, best_vendor = None, None
        for vendor in KNOWN_VENDORS:
            vm = re.search(r"\b" + re.escape(vendor) + r"\b", header, re.IGNORECASE)
            if vm and (best_pos is None or vm.start() < best_pos):
                best_pos, best_vendor = vm.start(), vendor
        if best_vendor:
            meta["vendor_name"] = best_vendor

    # Vendor from email domain (last resort).
    if not meta.get("vendor_name"):
        em = re.search(r"[\w._%+-]+@([\w]+)\.", text)
        if em:
            domain = em.group(1).capitalize()
            if domain.lower() not in (
                "gmail",
                "yahoo",
                "hotmail",
                "outlook",
                "google",
                "microsoft",
                "apple",
            ):
                meta["vendor_name"] = domain

    # VPAT edition.
    m = re.search(r"VPAT[®\s]*Version\s*([\d.]+)", text, re.IGNORECASE)
    if m:
        meta["vpat_edition"] = f"VPAT® Version {m.group(1)}"

    # Contact info — must look like actual contact data (email, phone, name).
    m = re.search(r"Contact\s+Information\s*:\s*(.+?)(?:\n\n|\Z)", text, re.IGNORECASE | re.DOTALL)
    if m:
        c = m.group(1).strip().split("\n")[0].strip()
        if c and len(c) < 150 and not is_blank_or_garbage(c) and re.search(r"[@.\w]{4,}", c):
            meta["vendor_contact"] = c

    # Email as contact fallback.
    if not meta.get("vendor_contact"):
        em = re.search(r"[\w._%+-]+@[\w.-]+\.[A-Z]{2,}", text, re.IGNORECASE)
        if em:
            meta["vendor_contact"] = em.group(0)

    # v9 FIX E: description regex must stop at the next cover-table key name,
    # otherwise it runs past the description into the date row.
    m = re.search(
        r"Product\s+Description\s*:\s*(.+?)"
        r"(?:\n(?:Date|Contact|Notes|Evaluation|Name|Version|Vendor)\s*:"
        r"|\nContact|\nNotes|\nEvaluation|\n\n|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        d = m.group(1).strip()
        if not is_blank_or_garbage(d) and len(d) > 30:
            d = clean_extracted_text(d)[:800]
            meta["product_description"] = d

    # Evaluation methods — strip watermarks/boilerplate.
    m = re.search(
        r"Evaluation\s+Methods?\s+Used\s*:\s*(.+?)(?:\n(?:Applicable|Standards|Table\s+\d|Terms)\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        methods = clean_extracted_text(m.group(1).strip())
        methods = re.sub(r'"Voluntary Product Accessibility Template"[^\n]*\n?', "", methods)
        methods = re.sub(r"[^\n]*VPAT[^\n]*registered[^\n]*\n?", "", methods, flags=re.IGNORECASE)
        methods = re.sub(r"service marks of[^\n]*\n?", "", methods, flags=re.IGNORECASE)
        methods = re.sub(
            r"Information Technology Industry[^\n]*\n?", "", methods, flags=re.IGNORECASE
        )
        methods = re.sub(r"Page\s+\d+\s+of\s+\d+[^\n]*\n?", "", methods, flags=re.IGNORECASE)
        methods = re.sub(r"\n{3,}", "\n\n", methods).strip()
        if methods and len(methods) > 20:
            meta["evaluation_methods"] = methods[:2000]

    # Product type.
    if re.search(r"web\s*app|web\s*portal|website|software", text, re.IGNORECASE):
        meta["product_type"] = "Web Application / Software"

    return meta


def _clean_product_name(raw: str) -> str:
    if not raw:
        return raw
    cleaned = re.sub(r"\s+\d{4}\s+Q\d\b", "", raw, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+VPAT\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+v[\d.]+\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+\d{4}-\d{2}-\d{2}.*$", "", cleaned).strip()
    return cleaned if cleaned else raw
