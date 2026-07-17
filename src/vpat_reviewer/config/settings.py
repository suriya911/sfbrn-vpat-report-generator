"""Unified settings store — organization identity *and* the grading policy.

Everything the user can edit lives in a single ``settings.json``:

* Identity fields (org name, reviewer, threshold, logo, report title) at the top
  level — the same schema the v10 GUI already reads.
* The Amazon Bedrock review settings, also at the top level.
* The editable grading policy under a ``"grading"`` key.

Saves are non-destructive: writing identity fields preserves the grading policy
and vice-versa, so neither editor can clobber the other. The legacy
``settings_manager`` module delegates here, so there is exactly one store.

**No key here may ever hold a credential.** ``settings.json`` is tracked in git
and the frozen app writes it beside the exe, so anything stored here is
published. There is deliberately no field a token could go in, and
``BedrockConfig`` ignores one if you add it by hand. See ``ai/bedrock.py``.
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
    # Which renderer Generate Report uses: "one_page" (the decision sheet the
    # client asked for) or "full" (~26 pages of evidence). See
    # reporting.renderer_for. One page is the default because it is what the
    # client requested; a reviewer who needs the evidence switches to "full" in
    # Settings, and the full report is still what the one-pager's footer points
    # at. Note renderer_for() falls back to "full" for an *unrecognized* value —
    # a different question from the default, and a typo should not silently give
    # a reviewer less of the review than they asked for.
    "report_style": "one_page",
    # Amazon Bedrock AI review (outer adapter). On by default: the shipped app
    # asks Bedrock for the verdict. use_ai=False falls back to the deterministic
    # classifier and keeps the app fully offline. Env vars override these at
    # runtime: VPAT_BEDROCK_REGION / VPAT_BEDROCK_MODEL_ID / VPAT_BEDROCK_PROFILE.
    #
    # There is no credential key here, and that is deliberate — see the module
    # docstring. The bearer token comes from env AWS_BEARER_TOKEN_BEDROCK or
    # VPAT_BEDROCK_API_KEY, from a gitignored `bedrock_api_key.txt` beside this
    # file, or use an AWS profile via bedrock_profile (a profile *name* is not a
    # secret). `bedrock_model_id` duplicates ai/bedrock.py::DEFAULT_MODEL_ID
    # because config cannot import ai; a test pins them together.
    "use_ai": True,
    "bedrock_region": "us-west-2",
    # Amazon Nova 2 Lite: cheapest and near-fastest of everything measured, and
    # it tracks the larger models' verdicts. The `us.` prefix is its inference
    # profile and is required — Converse rejects the bare catalog id. See
    # ai/bedrock.py::DEFAULT_MODEL_ID for the measurements and the caveats.
    "bedrock_model_id": "us.amazon.nova-2-lite-v1:0",
    "bedrock_profile": "",
    "bedrock_max_tokens": 4096,
    "bedrock_temperature": 0.2,
    # The CSV audit trail: one row per review. An empty path means the default —
    # `vpat_review_log.csv` inside ~/Downloads/VPAT Reviewer Files, beside the
    # reports (see user_files_dir). Set a path to put it elsewhere, e.g. a shared
    # drive; VPAT_AUDIT_LOG_PATH overrides both. The log never gates a review: an
    # unwritable path costs the row and logs a warning.
    "audit_log_enabled": True,
    "audit_log_path": "",
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


#: The folder every user-facing artefact goes in, under the user's Downloads.
USER_FILES_DIRNAME = "VPAT Reviewer Files"


def user_files_dir() -> Path:
    """The one folder this app writes to: ``~/Downloads/VPAT Reviewer Files``.

    Reports, copied VPATs, the AI prompt/response logs, and the audit CSV all
    live here, so a reviewer has one place to look and one folder to hand over.

    ``Path.home()`` resolves correctly on Windows and macOS alike, at call time
    rather than import time -- so the frozen exe is right on every machine it is
    copied to, not just the one it was built on.

    **Single source of truth on purpose.** The GUI and the audit log both need
    this, and they used to hardcode it separately: change one and the log
    silently orphans itself from the reports it describes. Same duplication
    hazard as the Bedrock model id (see ai/bedrock.py), which is why it lives in
    exactly one place instead. `config/` imports only `domain/`, so both `ui/`
    and `audit/` can depend on it without bending the arrows.
    """
    return Path.home() / "Downloads" / USER_FILES_DIRNAME


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
