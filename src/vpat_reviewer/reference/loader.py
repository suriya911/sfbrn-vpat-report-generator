"""WCAG reference data access.

The data itself lives in ``reference/data/wcag.json`` — one entry per WCAG
criterion with its title, level, principle, official description, plain-language
explanation, and interim workarounds. Editing that JSON (not code) updates the
reference the report quotes. This module just loads and serves it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

# The WCAG 2.1 Level A & AA criteria (plus the WCAG 2.2 additions the app tracks)
# that the reference dataset must cover to be considered complete.
REQUIRED_IDS: tuple[str, ...] = (
    "1.1.1",
    "1.2.1",
    "1.2.2",
    "1.2.3",
    "1.2.4",
    "1.2.5",
    "1.3.1",
    "1.3.2",
    "1.3.3",
    "1.3.4",
    "1.3.5",
    "1.4.1",
    "1.4.2",
    "1.4.3",
    "1.4.4",
    "1.4.5",
    "1.4.10",
    "1.4.11",
    "1.4.12",
    "1.4.13",
    "2.1.1",
    "2.1.2",
    "2.1.4",
    "2.2.1",
    "2.2.2",
    "2.3.1",
    "2.4.1",
    "2.4.2",
    "2.4.3",
    "2.4.4",
    "2.4.5",
    "2.4.6",
    "2.4.7",
    "2.4.11",
    "2.5.1",
    "2.5.2",
    "2.5.3",
    "2.5.4",
    "2.5.7",
    "2.5.8",
    "3.1.1",
    "3.1.2",
    "3.2.1",
    "3.2.2",
    "3.2.3",
    "3.2.4",
    "3.2.6",
    "3.3.1",
    "3.3.2",
    "3.3.3",
    "3.3.4",
    "3.3.7",
    "3.3.8",
    "4.1.1",
    "4.1.2",
    "4.1.3",
)


@lru_cache(maxsize=1)
def all_criteria() -> dict[str, dict[str, Any]]:
    """The full WCAG reference dataset, keyed by criterion id (cached)."""
    resource = files("vpat_reviewer.reference") / "data" / "wcag.json"
    data: dict[str, dict[str, Any]] = json.loads(resource.read_text(encoding="utf-8"))
    return data


def lookup(cid: str) -> dict[str, Any] | None:
    """Full reference entry for a criterion, or ``None`` if unknown."""
    if not cid:
        return None
    return all_criteria().get(str(cid).strip())


def has_all_required() -> tuple[bool, list[str]]:
    """``(all_present, missing_ids)`` — every required criterion must have a description."""
    data = all_criteria()
    missing = [c for c in REQUIRED_IDS if c not in data or not data[c].get("description")]
    return (len(missing) == 0, missing)


def title(cid: str) -> str:
    entry = lookup(cid)
    return entry["title"] if entry else ""


def workarounds(cid: str) -> list[str]:
    entry = lookup(cid)
    return list(entry["workarounds"]) if entry and entry.get("workarounds") else []
