"""
Settings Manager — v10
======================
Stores reviewer/organization identity so anyone (not just SFBRN / Jonathan
Hale) can use the VPAT Reviewer. Settings live in a local `settings.json`
next to the application — fully offline, no cloud, no telemetry.

Fields:
    org_name        Full organization name shown on the cover and footer.
    org_short       Short name/acronym used in the header block and prose.
    reviewer_name   Person preparing the report.
    reviewer_title  Their title (default: Accessibility Compliance Reviewer).
    org_contact     Contact line printed in the cover meta box (optional).
    threshold       Compliance threshold percentage (default 90).
    logo_path       Optional custom logo image; blank = bundled default logo.

First-run behavior: if settings.json does not exist, the app shows the setup
dialog before the main window so the report never ships with someone else's
name on it by accident.
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULTS = {
    "org_name":       "San Francisco Bay Region Network (SFBRN)",
    "org_short":      "SFBRN",
    "reviewer_name":  "Jonathan Hale",
    "reviewer_title": "Accessibility Compliance Reviewer",
    "org_contact":    "",
    "threshold":      90,
    "logo_path":      "",
    "report_title":   "VPAT Accessibility Compliance \u2014 Summary Report",
}

FIELD_LABELS = [
    ("org_name",       "Organization name (full)"),
    ("org_short",      "Organization short name / acronym"),
    ("reviewer_name",  "Reviewer name"),
    ("reviewer_title", "Reviewer title"),
    ("org_contact",    "Organization contact (email/phone, optional)"),
    ("threshold",      "Compliance threshold % (default 90)"),
]


def settings_path() -> Path:
    """settings.json lives next to the application files. When packaged with
    PyInstaller, that means next to the installed .exe (the app installs to
    the user's LocalAppData folder, which is always writable)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "settings.json"
    return Path(__file__).resolve().parent / "settings.json"


def load_settings() -> dict:
    """Load settings, falling back to defaults for any missing field."""
    s = dict(DEFAULTS)
    p = settings_path()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in DEFAULTS:
                if k in data and data[k] not in (None, ""):
                    s[k] = data[k]
        except Exception as e:
            logger.warning("Could not read settings.json: %s", e)
    try:
        s["threshold"] = max(0, min(100, int(s["threshold"])))
    except (TypeError, ValueError):
        s["threshold"] = 90
    return s


def save_settings(values: dict) -> bool:
    """Persist settings locally. Returns True on success."""
    s = load_settings()
    s.update({k: v for k, v in values.items() if k in DEFAULTS})
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error("Could not save settings.json: %s", e)
        return False


def is_first_run() -> bool:
    return not settings_path().exists()
