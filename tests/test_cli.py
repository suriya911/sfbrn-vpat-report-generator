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
    assert out["score"] == 50
    assert out["score_detail"]["supported"] == 2
    assert out["barriers"] == ["1.4.3", "2.4.7"]
    assert out["document_kind"] == "vpat"


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


def test_review_writes_the_json_record_beside_the_pdf(tmp_path: Path):
    out = tmp_path / "cli.pdf"
    assert main(["review", FIXTURE, "-o", str(out)]) == 0
    record = tmp_path / "cli.json"
    assert record.exists(), "the machine-readable record should ship with the report"
    assert json.loads(record.read_text(encoding="utf-8"))["criteria"]


def test_review_no_json_suppresses_the_record(tmp_path: Path):
    out = tmp_path / "cli.pdf"
    assert main(["review", FIXTURE, "-o", str(out), "--no-json"]) == 0
    assert not (tmp_path / "cli.json").exists()


def test_review_json_out_honours_an_explicit_path(tmp_path: Path):
    out = tmp_path / "cli.pdf"
    record = tmp_path / "elsewhere.json"
    assert main(["review", FIXTURE, "-o", str(out), "--json-out", str(record)]) == 0
    assert record.exists()


def test_non_vpat_is_refused_with_a_distinct_exit_code(tmp_path: Path, capsys):
    """Exit 2 means "wrong kind of file"; exit 1 means "a VPAT we could not read".

    Scoring a remediation plan produces an authoritative-looking number that
    means nothing, so refuse rather than report.
    """
    taap = tmp_path / "plan.txt"
    taap.write_text(
        "Temporary Alternative Access Plan (TAAP)\nKnown Accessibility Barriers\n",
        encoding="utf-8",
    )
    assert main(["analyze", str(taap)]) == 2
    assert "does not look like a VPAT" in capsys.readouterr().err

    out = tmp_path / "nope.pdf"
    assert main(["review", str(taap), "-o", str(out)]) == 2
    assert not out.exists(), "a refused document must not produce a report"


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
