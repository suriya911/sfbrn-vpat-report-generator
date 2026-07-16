"""Unified settings store — organization identity *and* the grading policy.

Everything the user can edit lives in a single ``settings.json``:

* Identity fields (org name, reviewer, threshold, logo, report title) at the top
  level — the same schema the v10 GUI already reads.
* The editable grading policy under a ``"grading"`` key.

Saves are non-destructive: writing identity fields preserves the grading policy
and vice-versa, so neither editor can clobber the other. The legacy
``settings_manager`` module delegates here, so there is exactly one store.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vpat_reviewer.domain.policy import GradingPolicy

logger = logging.getLogger(__name__)

IDENTITY_DEFAULTS: dict[str, Any] = {
    "org_name": "San Francisco Bay Region Network (SFBRN)",
    "org_short": "SFBRN",
    "reviewer_name": "Jonathan Hale",
    "reviewer_title": "Accessibility Compliance Reviewer",
    "org_contact": "",
    "threshold": 90,
    "logo_path": "",
    "report_title": "VPAT Accessibility Compliance — Summary Report",
    # Which renderer Generate Report uses: "full" (~26 pages of evidence) or
    # "one_page" (the decision sheet). See reporting.renderer_for.
    "report_style": "full",
    # Amazon Bedrock AI review (outer adapter). use_ai=False keeps the app fully
    # offline (deterministic scoring only). Env vars override these at runtime:
    # VPAT_BEDROCK_REGION / VPAT_BEDROCK_MODEL_ID / VPAT_BEDROCK_PROFILE.
    "use_ai": True,
    "bedrock_region": "us-west-2",
    "bedrock_model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "bedrock_profile": "",
    # Bedrock API key (bearer token). Preferred for sharing across a team: set it
    # here, in env AWS_BEARER_TOKEN_BEDROCK, or drop a `bedrock_api_key.txt` file
    # next to settings.json. Takes precedence over bedrock_profile.
    "bedrock_api_key": "",
    "bedrock_api_key_file": "",
}

FIELD_LABELS: list[tuple[str, str]] = [
    ("org_name", "Organization name (full)"),
    ("org_short", "Organization short name / acronym"),
    ("reviewer_name", "Reviewer name"),
    ("reviewer_title", "Reviewer title"),
    ("org_contact", "Organization contact (email/phone, optional)"),
    ("threshold", "Compliance threshold % (default 90)"),
]

_GRADING_KEY = "grading"


def _project_root() -> Path:
    # src/vpat_reviewer/config/settings.py -> parents[3] == the project root.
    return Path(__file__).resolve().parents[3]


def default_settings_path() -> Path:
    """Where settings.json lives.

    Override with ``VPAT_SETTINGS_PATH`` (used by tests). When frozen by
    PyInstaller, next to the executable (LocalAppData install dir is writable).
    Otherwise the project root.
    """
    override = os.environ.get("VPAT_SETTINGS_PATH")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "settings.json"
    return _project_root() / "settings.json"


# Legacy alias.
def settings_path() -> Path:
    return default_settings_path()


def _read_all(path: Path | None = None) -> dict[str, Any]:
    p = path or default_settings_path()
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001 — corrupt file must not crash the app.
        logger.warning("Could not read settings.json: %s", e)
        return {}


def _write_all(data: dict[str, Any], path: Path | None = None) -> bool:
    p = path or default_settings_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Could not save settings.json: %s", e)
        return False


# ── Identity settings (legacy-shaped dict) ────────────────────────────────────


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Return identity settings merged over defaults, with threshold coerced."""
    s = dict(IDENTITY_DEFAULTS)
    data = _read_all(path)
    for k in IDENTITY_DEFAULTS:
        if k in data and data[k] not in (None, ""):
            s[k] = data[k]
    try:
        s["threshold"] = max(0, min(100, int(s["threshold"])))
    except (TypeError, ValueError):
        s["threshold"] = 90
    return s


def save_settings(values: dict[str, Any], path: Path | None = None) -> bool:
    """Persist identity fields, preserving the grading policy and any other keys."""
    data = _read_all(path)
    for k, v in values.items():
        if k in IDENTITY_DEFAULTS:
            data[k] = v
    return _write_all(data, path)


# ── Grading policy ────────────────────────────────────────────────────────────


def load_policy(path: Path | None = None) -> GradingPolicy:
    """Load the editable grading policy, inheriting defaults for anything unset."""
    return GradingPolicy.from_dict(_read_all(path).get(_GRADING_KEY))


def save_policy(policy: GradingPolicy, path: Path | None = None) -> bool:
    """Persist the grading policy, preserving identity fields and any other keys."""
    data = _read_all(path)
    data[_GRADING_KEY] = policy.to_dict()
    return _write_all(data, path)


def is_first_run(path: Path | None = None) -> bool:
    p = path or default_settings_path()
    return not p.exists()


# ── Bundle convenience for new code ───────────────────────────────────────────


@dataclass
class Settings:
    identity: dict[str, Any]
    policy: GradingPolicy


def load(path: Path | None = None) -> Settings:
    return Settings(identity=load_settings(path), policy=load_policy(path))
