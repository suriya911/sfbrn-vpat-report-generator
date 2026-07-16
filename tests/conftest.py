"""Suite-wide guards.

The rule these enforce: **a test must not touch the developer's own machine.**
The suite already avoids the network (see CLAUDE.md §8); the audit log added the
mirror-image hazard on the write side, and it is easy to reintroduce because the
polluting test looks entirely innocent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vpat_reviewer.audit.csv_log import PATH_ENV


@pytest.fixture(autouse=True)
def _never_write_the_real_audit_log(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point every test's audit log at a temp file.

    Without this, anything that drives a review through a composition root --
    `tests/test_cli.py` most obviously -- appends fixture rows ("Acme Learn",
    paths under `tests/`) to the real `vpat_review_log.csv` on the developer's
    Desktop. That file is a reviewer's audit trail of actual procurement
    decisions, so the test suite silently forges records in it.

    Autouse and suite-wide because the danger is not in the tests that mean to
    log -- it is in the ones that have no idea they do.
    """
    path = tmp_path_factory.mktemp("audit") / "vpat_review_log.csv"
    monkeypatch.setenv(PATH_ENV, str(path))
    return path
