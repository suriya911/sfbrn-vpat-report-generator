"""The audit log's contract: it records faithfully, and it never breaks a review."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from vpat_reviewer.audit import FIELDS, AuditEvent, AuditLog, CsvAuditLog, log_for
from vpat_reviewer.audit.csv_log import PATH_ENV, _defuse, default_log_path


def _rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_satisfies_the_port() -> None:
    assert isinstance(CsvAuditLog("x.csv"), AuditLog)


def test_records_a_row_with_every_column(tmp_path: Path) -> None:
    out = tmp_path / "log.csv"
    CsvAuditLog(out).record(AuditEvent.of(product_name="Acme Learn", score=72))

    rows = _rows(out)
    assert len(rows) == 1
    assert rows[0]["product_name"] == "Acme Learn"
    assert rows[0]["score"] == "72"
    assert set(rows[0]) == set(FIELDS)


def test_appends_without_repeating_the_header(tmp_path: Path) -> None:
    out = tmp_path / "log.csv"
    log = CsvAuditLog(out)
    log.record(AuditEvent.of(product_name="First"))
    log.record(AuditEvent.of(product_name="Second"))

    assert [r["product_name"] for r in _rows(out)] == ["First", "Second"]
    assert out.read_text(encoding="utf-8-sig").count("product_name") == 1


def test_creates_the_folder_it_logs_into(tmp_path: Path) -> None:
    out = tmp_path / "VPAT Reviewer Files" / "log.csv"
    CsvAuditLog(out).record(AuditEvent.of(product_name="Acme"))

    assert out.exists()


def test_an_unwritable_log_does_not_raise(tmp_path: Path) -> None:
    """The reviewer has the CSV open in Excel. That must cost the row, not the review."""
    out = tmp_path / "log.csv"
    out.mkdir()  # a directory where the file should be: every write will fail

    CsvAuditLog(out).record(AuditEvent.of(product_name="Acme"))  # must not raise


def test_unreported_values_stay_empty_rather_than_becoming_none(tmp_path: Path) -> None:
    """ "Not reported" and a value are different facts -- the string "None" is neither."""
    out = tmp_path / "log.csv"
    CsvAuditLog(out).record(AuditEvent.of(input_tokens=None, score=0))

    row = _rows(out)[0]
    assert row["input_tokens"] == ""
    assert row["score"] == "0"  # a real zero survives; only unknowns are blank


def test_a_column_that_does_not_exist_is_a_mistake_not_a_silent_drop() -> None:
    import pytest

    with pytest.raises(ValueError, match="tokens_used"):
        AuditEvent.of(tokens_used=5)


def test_vendor_text_cannot_smuggle_a_formula_into_the_spreadsheet() -> None:
    """Vendor-controlled text lands in cells a reviewer opens in Excel.

    Same untrusted-input problem as the ReportLab markup trap: the product name
    comes from the vendor's document, and a leading '=' makes Excel evaluate the
    cell rather than show it.
    """
    assert _defuse("=cmd|'/c calc'!A1").startswith("'=")
    assert _defuse("+1+1") == "'+1+1"
    assert _defuse("@SUM(A1)") == "'@SUM(A1)"
    assert _defuse("Acme Learn") == "Acme Learn"  # ordinary text is untouched


def test_the_default_log_lands_beside_the_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolved per machine, so the shipped exe is right on every reviewer's."""
    monkeypatch.delenv(PATH_ENV, raising=False)  # the suite-wide guard sets it
    path = default_log_path()
    assert path.parent.name == "VPAT Reviewer Files"
    assert path.parent.parent.name == "Desktop"
    assert path.suffix == ".csv"


def test_the_env_override_wins_over_the_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The local lever beats the shared one.

    ``audit_log_path`` lives in settings.json, which is committed and ships to
    every reviewer; the env var is per-machine. This precedence is also what
    stops the suite writing fixture rows into a developer's real Desktop log --
    see tests/conftest.py.
    """
    monkeypatch.setenv(PATH_ENV, str(tmp_path / "redirected.csv"))
    assert default_log_path() == tmp_path / "redirected.csv"

    log = log_for({"audit_log_path": r"C:\Users\someone\Desktop\real.csv"})
    assert log is not None
    assert log.path == tmp_path / "redirected.csv"

    # "Switched off" still means off: the override says *where*, not *whether*.
    assert log_for({"audit_log_enabled": False}) is None


def test_log_for_honors_the_setting() -> None:
    assert log_for({"audit_log_enabled": False}) is None
    assert isinstance(log_for({}), CsvAuditLog)
    assert isinstance(log_for(None), CsvAuditLog)


def test_log_for_uses_a_configured_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PATH_ENV, raising=False)  # the suite-wide guard sets it
    log = log_for({"audit_log_path": str(tmp_path / "shared.csv")})
    assert log is not None
    assert log.path == tmp_path / "shared.csv"


def test_an_empty_configured_path_means_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PATH_ENV, raising=False)
    log = log_for({"audit_log_path": ""})
    assert log is not None
    assert log.path == default_log_path()
