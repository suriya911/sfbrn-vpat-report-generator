"""Headless self-test for the packaged app.

The GUI executable can't show terminal output, so ``VPAT_Reviewer.exe
--selftest`` runs these checks *inside the frozen app* and writes the result to
a JSON file. Use it to confirm a fresh build actually works — most importantly
that the bundled WCAG reference data (``wcag.json``) is present and loadable,
which is the one thing packaging tends to break.

    VPAT_Reviewer.exe --selftest                 -> writes vpat_selftest.json next to the exe
    VPAT_Reviewer.exe --selftest C:\\path\\out.json -> writes to a chosen path

From source you can run the same checks with a console::

    python run_app.py --selftest
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vpat_reviewer import __version__
from vpat_reviewer.config import settings
from vpat_reviewer.domain.policy import GradingPolicy
from vpat_reviewer.reference import loader


def run_checks() -> dict[str, Any]:
    """Run every self-check and return a structured, JSON-serializable result."""
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    # 1. WCAG reference data is bundled and loads (the packaging-critical check).
    try:
        data = loader.all_criteria()
        record("wcag_data_loads", bool(data), f"{len(data)} criteria loaded")
    except Exception as e:  # noqa: BLE001 — report, don't crash the self-test.
        record("wcag_data_loads", False, f"{type(e).__name__}: {e}")

    # 2. The dataset covers every required criterion.
    try:
        ok, missing = loader.has_all_required()
        record("wcag_data_complete", ok, "all required present" if ok else f"missing: {missing}")
    except Exception as e:  # noqa: BLE001
        record("wcag_data_complete", False, f"{type(e).__name__}: {e}")

    # 3. The default grading policy is valid.
    try:
        problems = GradingPolicy.default().validate()
        record("default_policy_valid", not problems, "; ".join(problems) or "valid")
    except Exception as e:  # noqa: BLE001
        record("default_policy_valid", False, f"{type(e).__name__}: {e}")

    # 4. The saved policy (settings.json, if any) is valid.
    try:
        problems = settings.load_policy().validate()
        record("saved_policy_valid", not problems, "; ".join(problems) or "valid")
    except Exception as e:  # noqa: BLE001
        record("saved_policy_valid", False, f"{type(e).__name__}: {e}")

    # 5. The report renderer imports (its heavy deps are bundled).
    try:
        from vpat_reviewer.reporting import ReportLabRenderer

        record("renderer_imports", True, ReportLabRenderer().output_suffix)
    except Exception as e:  # noqa: BLE001
        record("renderer_imports", False, f"{type(e).__name__}: {e}")

    passed = all(c["ok"] for c in checks)
    return {
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "passed": passed,
        "checks": checks,
    }


def run_selftest(argv: Sequence[str]) -> int:
    """Run the checks and write the result to JSON. Returns 0 if all passed.

    ``argv`` is the full process argv; the first token after ``--selftest`` (if
    present) is used as the output path. Otherwise the result is written next to
    the settings file (i.e. next to the exe when frozen).
    """
    out_path: Path | None = None
    args = list(argv)
    if "--selftest" in args:
        i = args.index("--selftest")
        if i + 1 < len(args) and not args[i + 1].startswith("-"):
            out_path = Path(args[i + 1])
    if out_path is None:
        out_path = settings.default_settings_path().with_name("vpat_selftest.json")

    result = run_checks()
    with contextlib.suppress(OSError):  # Best-effort; exit code still reflects the result.
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # When a console is attached (running from source), also print.
    if not getattr(sys, "frozen", False):
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["passed"] else 1
