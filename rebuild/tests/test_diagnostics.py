"""Tests for the packaged-app self-test (`diagnostics`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vpat_reviewer import __version__, diagnostics


def test_run_checks_all_pass() -> None:
    result = diagnostics.run_checks()
    assert result["passed"] is True, result
    names = {c["name"] for c in result["checks"]}
    assert {
        "wcag_data_loads",
        "wcag_data_complete",
        "default_policy_valid",
        "saved_policy_valid",
        "renderer_imports",
    } <= names
    assert all(c["ok"] for c in result["checks"])
    assert result["version"] == __version__


def test_run_selftest_writes_json_and_returns_zero(tmp_path: Path) -> None:
    out = tmp_path / "selftest.json"
    code = diagnostics.run_selftest(["--selftest", str(out)])
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["passed"] is True


def test_run_selftest_defaults_output_next_to_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Point the settings store at a temp dir; the default output lands beside it.
    monkeypatch.setenv("VPAT_SETTINGS_PATH", str(tmp_path / "settings.json"))
    code = diagnostics.run_selftest([])
    assert code == 0
    assert (tmp_path / "vpat_selftest.json").exists()
