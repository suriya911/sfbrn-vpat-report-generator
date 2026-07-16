"""Dev-only scoreboard: run the parser over a corpus of real VPATs and report
what it did — coverage, status resolution, unknown phrasings, and invariant
violations.

This is the iteration loop for parser work. It is **not** shipped: ``tools/`` is
outside the packaged ``src/vpat_reviewer`` (see ``pyproject.toml``), so it cannot
end up in the wheel or the frozen exe.

Usage::

    python tools/corpus_report.py docs/completed_forms
    python tools/corpus_report.py docs/completed_forms --json .corpus/report.json
    python tools/corpus_report.py --check          # diff vs the committed baseline

``--check`` compares against ``tools/corpus_baseline.json`` and exits non-zero on
any regression, so a parser change that quietly loses coverage fails loudly.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Make `src/` importable when run straight from the project root.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from vpat_reviewer.domain.models import VPATDocument  # noqa: E402
from vpat_reviewer.parsing.criteria import WCAG_LEVELS  # noqa: E402
from vpat_reviewer.parsing.document import parse_vpat  # noqa: E402

BASELINE_PATH = _ROOT / "tools" / "corpus_baseline.json"
PARSEABLE = (".pdf", ".docx", ".doc", ".txt")

# How many A/AA success criteria each WCAG version defines. Used to sanity-check
# coverage against whatever standard the vendor claims to have reviewed.
EXPECTED_AA_COUNTS = {"2.0": 38, "2.1": 50, "2.2": 56}


@dataclass
class FileReport:
    """Everything worth knowing about one document's parse."""

    name: str
    error: str = ""
    kind: str = ""
    kind_reasons: list[str] = field(default_factory=list)
    wcag_count: int = 0
    fpc_count: int = 0
    ch6_count: int = 0
    product_name: str = ""
    vendor_name: str = ""
    standards: list[str] = field(default_factory=list)
    statuses: dict[str, int] = field(default_factory=dict)
    levels: dict[str, int] = field(default_factory=dict)
    unresolved: int = 0
    unknown_phrasings: dict[str, int] = field(default_factory=dict)
    missing_ids: list[str] = field(default_factory=list)
    unexpected_ids: list[str] = field(default_factory=list)
    empty_remarks: int = 0
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _ids_in_text(text: str) -> set[str]:
    """Every known WCAG id that literally appears in the raw text."""
    found = set()
    for m in re.finditer(r"\b(\d+\.\d+\.\d+)\b", text):
        if m.group(1) in WCAG_LEVELS:
            found.add(m.group(1))
    return found


def _check_invariants(doc: VPATDocument, rep: FileReport) -> None:
    """Structural properties that must hold regardless of ground truth."""
    wcag = [c for c in doc.criteria if c.section == "wcag"]

    # I2 — every wcag id must be a real WCAG success criterion.
    bad = sorted({c.criterion_id for c in wcag if c.criterion_id not in WCAG_LEVELS})
    if bad:
        rep.violations.append(f"I2 non-WCAG ids parsed as wcag: {bad[:8]}")
        rep.unexpected_ids = bad

    # I3 — the parsed level must agree with the canonical level for that id.
    for c in wcag:
        canon = WCAG_LEVELS.get(c.criterion_id)
        if canon and c.level and c.level != canon:
            rep.violations.append(f"I3 level mismatch {c.criterion_id}: {c.level} != {canon}")

    # I4 — no duplicate ids within a section.
    dupes = [i for i, n in Counter(c.criterion_id for c in wcag).items() if n > 1]
    if dupes:
        rep.violations.append(f"I4 duplicate ids: {sorted(dupes)[:8]}")

    # I1 (soundness) — a status we report must actually appear in the source.
    # Catches rows synthesized from nothing.
    text_lower = doc.raw_text.lower()
    for c in doc.criteria:
        if c.raw_status and c.raw_status.lower() not in text_lower:
            rep.violations.append(
                f"I1 status not found in source: {c.criterion_id}={c.raw_status!r}"
            )
            break
    fabricated = [c for c in doc.criteria if c.section == "508_fpc" and not c.raw_status]
    if fabricated:
        rep.violations.append(
            f"I1 {len(fabricated)} 508_fpc rows with no source status (synthesized?)"
        )

    # Recall — ids present in the text but never parsed.
    present = _ids_in_text(doc.raw_text)
    parsed = {c.criterion_id for c in wcag}
    missing = sorted(present - parsed, key=lambda s: [int(p) for p in s.split(".")])
    if missing:
        rep.missing_ids = missing


def analyze_file(path: Path) -> FileReport:
    rep = FileReport(name=path.name)
    try:
        doc = parse_vpat(str(path))
    except Exception as e:  # noqa: BLE001 — a dev tool must survive any input.
        rep.error = f"{type(e).__name__}: {e}"
        return rep

    wcag = [c for c in doc.criteria if c.section == "wcag"]
    rep.kind = doc.document_kind.value
    rep.kind_reasons = list(doc.document_kind_reasons)
    rep.wcag_count = len(wcag)
    rep.fpc_count = sum(1 for c in doc.criteria if c.section == "508_fpc")
    rep.ch6_count = sum(1 for c in doc.criteria if c.section == "508_ch6")
    rep.product_name = doc.product_name
    rep.vendor_name = doc.vendor_name
    rep.standards = list(doc.standards_reviewed)
    rep.warnings = list(doc.parse_warnings)
    rep.statuses = dict(Counter(c.normalized_status for c in wcag).most_common())
    rep.levels = dict(Counter(c.level or "?" for c in wcag).most_common())
    rep.empty_remarks = sum(1 for c in wcag if not c.remarks.strip())

    # A row whose raw status is blank had no status recovered at all — that is
    # the signature of a column-index miss, and the number to watch.
    rep.unresolved = sum(1 for c in wcag if not c.raw_status.strip())

    # Raw phrasings that normalize to Not Evaluated without literally saying so:
    # the vendor wrote something we do not understand.
    unknown: Counter[str] = Counter()
    for c in wcag:
        raw = c.raw_status.strip()
        if not raw:
            continue
        if c.normalized_status == "Not Evaluated" and "not evaluated" not in raw.lower():
            unknown[raw] += 1
    rep.unknown_phrasings = dict(unknown.most_common(10))

    _check_invariants(doc, rep)
    return rep


def _fmt_counts(d: dict[str, int]) -> str:
    if not d:
        return "-"
    return " ".join(f"{k}={v}" for k, v in d.items())


def print_report(reports: list[FileReport]) -> None:
    print("=" * 100)
    print("VPAT CORPUS REPORT")
    print("=" * 100)
    print(f"{'file':<40} {'kind':<15} {'wcag':>5} {'fpc':>4} {'unres':>6} {'viol':>5}")
    print("-" * 100)
    for r in reports:
        if r.error:
            print(f"{r.name[:39]:<40} ERROR {r.error[:44]}")
            continue
        flag = "!" if r.unresolved else " "
        print(
            f"{r.name[:39]:<40} {r.kind:<15} {r.wcag_count:>5} {r.fpc_count:>4} "
            f"{r.unresolved:>5}{flag} {len(r.violations):>5}"
        )

    print()
    print("=" * 100)
    print("DETAIL")
    print("=" * 100)
    for r in reports:
        if r.error:
            continue
        notable = r.violations or r.unknown_phrasings or r.missing_ids or r.unresolved
        if not notable:
            continue
        print(f"\n{r.name}  [{r.kind}]")
        if r.kind_reasons:
            print(f"  because: {'; '.join(r.kind_reasons)}")
        print(f"  product={r.product_name[:60]!r} vendor={r.vendor_name!r}")
        print(f"  statuses={_fmt_counts(r.statuses)}")
        if r.unresolved:
            print(f"  !! {r.unresolved}/{r.wcag_count} rows have NO raw status recovered")
        if r.unknown_phrasings:
            print(f"  unknown phrasings: {r.unknown_phrasings}")
        if r.missing_ids:
            print(f"  ids in text but not parsed ({len(r.missing_ids)}): {r.missing_ids[:12]}")
        for v in r.violations[:6]:
            print(f"  VIOLATION {v}")
        if r.warnings:
            print(f"  warnings: {r.warnings}")

    total_unres = sum(r.unresolved for r in reports if not r.error)
    total_viol = sum(len(r.violations) for r in reports if not r.error)
    total_wcag = sum(r.wcag_count for r in reports if not r.error)
    print()
    print("=" * 100)
    print(
        f"TOTALS: {len(reports)} files | {total_wcag} wcag rows | "
        f"{total_unres} unresolved | {total_viol} invariant violations"
    )
    print("=" * 100)


def _comparable(reports: list[FileReport]) -> dict[str, Any]:
    """The subset of the report that should be stable across runs."""
    return {
        r.name: {
            "wcag_count": r.wcag_count,
            "fpc_count": r.fpc_count,
            "unresolved": r.unresolved,
            "statuses": r.statuses,
            "violations": len(r.violations),
        }
        for r in reports
    }


def check_against_baseline(reports: list[FileReport]) -> int:
    if not BASELINE_PATH.exists():
        print(f"No baseline at {BASELINE_PATH}. Write one with --save-baseline.")
        return 1
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    current = _comparable(reports)
    failures: list[str] = []
    for name, want in baseline.items():
        got = current.get(name)
        if got is None:
            failures.append(f"{name}: missing from this run")
            continue
        if got["wcag_count"] < want["wcag_count"]:
            failures.append(f"{name}: coverage dropped {want['wcag_count']} -> {got['wcag_count']}")
        if got["unresolved"] > want["unresolved"]:
            failures.append(f"{name}: unresolved rose {want['unresolved']} -> {got['unresolved']}")
        if got["violations"] > want["violations"]:
            failures.append(f"{name}: violations rose {want['violations']} -> {got['violations']}")
    for f in failures:
        print(f"REGRESSION {f}")
    if failures:
        return 1
    print("No regressions vs baseline.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corpus", nargs="?", default="docs/completed_forms")
    ap.add_argument("--json", dest="json_out", help="write the full report as JSON")
    ap.add_argument("--check", action="store_true", help="fail on regression vs baseline")
    ap.add_argument("--save-baseline", action="store_true", help="overwrite the baseline")
    args = ap.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        print(f"Not a directory: {corpus}", file=sys.stderr)
        return 2

    paths = sorted(p for p in corpus.iterdir() if p.suffix.lower() in PARSEABLE)
    reports = [analyze_file(p) for p in paths]

    if not args.check:
        print_report(reports)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([asdict(r) for r in reports], indent=2), encoding="utf-8")
        print(f"\nWrote {out}")

    if args.save_baseline:
        BASELINE_PATH.write_text(
            json.dumps(_comparable(reports), indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"Wrote baseline {BASELINE_PATH}")

    if args.check:
        return check_against_baseline(reports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
