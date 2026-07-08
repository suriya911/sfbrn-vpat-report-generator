import json
from pathlib import Path

import pytest

from vpat_reviewer.cli import main

FIXTURE = str(Path(__file__).parent / "fixtures" / "txt" / "acme_basic.txt")


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    # Read a non-existent settings file so the CLI uses default policy/settings.
    monkeypatch.setenv("VPAT_SETTINGS_PATH", str(tmp_path / "settings.json"))


def test_version_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0


def test_analyze_json(capsys):
    rc = main(["analyze", FIXTURE, "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["product_name"] == "Acme Learn"
    assert out["score"]["score"] == 33
    assert out["barriers"] == ["1.4.3", "2.4.7"]


def test_analyze_summary(capsys):
    rc = main(["analyze", FIXTURE])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Score:" in out
    assert "Barriers" in out


def test_analyze_impact_flags(capsys):
    rc = main(["analyze", FIXTURE, "--access", "denies_access", "--legal", "high", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["impact"]["suggested_level"] == "High"


def test_review_creates_pdf(tmp_path: Path):
    out = tmp_path / "cli.pdf"
    rc = main(["review", FIXTURE, "-o", str(out)])
    assert rc == 0
    assert out.exists() and out.read_bytes()[:5] == b"%PDF-"


def test_policy_show(capsys):
    rc = main(["policy", "show"])
    assert rc == 0
    d = json.loads(capsys.readouterr().out)
    assert d["graded_level"] == "AA"
    assert len(d["score_bands"]) == 4


def test_policy_validate(capsys):
    assert main(["policy", "validate"]) == 0


def test_analyze_unsupported_returns_1():
    assert main(["analyze", "mystery.xlsx"]) == 1
