"""``vpat-review`` command-line interface — a thin adapter over the service.

Commands:
    vpat-review analyze INPUT [--json]          parse + score, no file output
    vpat-review review  INPUT [-o OUT] [--json] parse + score + render a PDF
    vpat-review policy  show|path|validate      inspect the editable grading policy

Impact answers can be supplied to review/analyze via --audience/--access/
--legal/--deployment; omitted answers fall back to the least-severe defaults.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vpat_reviewer import __version__, service
from vpat_reviewer.config import settings

_AUDIENCE = ["individual", "small_team", "department", "campus_wide"]
_ACCESS = ["no_limit", "limits_some", "denies_access"]
_LEGAL = ["low", "medium", "high"]
_DEPLOYMENT = ["individual", "small_team", "department", "campus_wide"]


def _answers(args: argparse.Namespace) -> dict[str, str]:
    out: dict[str, str] = {}
    if getattr(args, "audience", None):
        out["audience"] = args.audience
    if getattr(args, "access", None):
        out["access_impact"] = args.access
    if getattr(args, "legal", None):
        out["legal_exposure"] = args.legal
    if getattr(args, "deployment", None):
        out["deployment"] = args.deployment
    return out


def _add_impact_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--audience", choices=_AUDIENCE, help="Who is affected (impact input).")
    p.add_argument("--access", choices=_ACCESS, help="Access impact (impact input).")
    p.add_argument("--legal", choices=_LEGAL, help="Legal exposure (impact input).")
    p.add_argument("--deployment", choices=_DEPLOYMENT, help="Deployment scale (impact input).")


def _result_dict(result: service.ReviewResult) -> dict[str, Any]:
    doc = result.document
    return {
        "product_name": doc.product_name,
        "product_version": doc.product_version,
        "vendor_name": doc.vendor_name,
        "standards_reviewed": doc.standards_reviewed,
        "score": result.score,
        "impact": result.impact,
        "barriers": [b.criterion_id for b in result.barriers],
        "warnings": result.warnings,
        "output_path": result.output_path,
    }


def _print_summary(result: service.ReviewResult) -> None:
    doc = result.document
    name = f"{doc.product_name} {doc.product_version}".strip() or "(unknown product)"
    print(f"Product: {name}")
    if doc.vendor_name:
        print(f"Vendor:  {doc.vendor_name}")
    s = result.score
    if s["score"] is None:
        print(f"Score:   N/A — {s['message']}")
    else:
        print(
            f"Score:   {s['score']}% "
            f"({s['supported']}/{s['total']} reviewable AA supported, "
            f"{s['na_excluded']} N/A excluded)"
        )
    print(f"Impact:  {result.impact['suggested_level']}")
    ids = [b.criterion_id for b in result.barriers]
    print(f"Barriers ({len(ids)}): {', '.join(ids) if ids else 'none'}")
    if result.output_path:
        print(f"Report:  {result.output_path}")
    for w in result.warnings:
        print(f"  warning: {w}", file=sys.stderr)


def _emit(result: service.ReviewResult, as_json: bool) -> None:
    if as_json:
        print(json.dumps(_result_dict(result), indent=2, ensure_ascii=False))
    else:
        _print_summary(result)


def _cmd_analyze(args: argparse.Namespace) -> int:
    result = service.analyze(args.input, answers=_answers(args))
    _emit(result, args.json)
    return 0 if result.has_criteria else 1


def _default_output(input_path: str) -> str:
    p = Path(input_path)
    return str(p.with_name(f"{p.stem} - VPAT Report.pdf"))


def _cmd_review(args: argparse.Namespace) -> int:
    result = service.analyze(args.input, answers=_answers(args))
    if not result.has_criteria:
        _emit(result, args.json)
        print("Nothing to report — no criteria were parsed.", file=sys.stderr)
        return 1
    output = args.output or _default_output(args.input)
    service.render_result(result, output, logo_path=args.logo or "")
    _emit(result, args.json)
    return 0


def _cmd_policy_show(_args: argparse.Namespace) -> int:
    print(json.dumps(settings.load_policy().to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_policy_path(_args: argparse.Namespace) -> int:
    print(settings.default_settings_path())
    return 0


def _cmd_policy_validate(_args: argparse.Namespace) -> int:
    problems = settings.load_policy().validate()
    if not problems:
        print("Grading policy is valid.")
        return 0
    print("Grading policy has problems:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vpat-review", description="VPAT accessibility reviewer.")
    parser.add_argument("--version", action="version", version=f"vpat-review {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="Parse and score a VPAT (no file output).")
    p_analyze.add_argument("input", help="Path to the vendor VPAT (PDF/DOCX/TXT).")
    p_analyze.add_argument("--json", action="store_true", help="Emit JSON instead of a summary.")
    _add_impact_flags(p_analyze)
    p_analyze.set_defaults(func=_cmd_analyze)

    p_review = sub.add_parser("review", help="Generate a compliance report from a VPAT.")
    p_review.add_argument("input", help="Path to the vendor VPAT (PDF/DOCX/TXT).")
    p_review.add_argument("-o", "--output", help="Output PDF path (default: next to input).")
    p_review.add_argument("--logo", help="Path to a logo image for the report.")
    p_review.add_argument("--json", action="store_true", help="Emit JSON instead of a summary.")
    _add_impact_flags(p_review)
    p_review.set_defaults(func=_cmd_review)

    p_policy = sub.add_parser("policy", help="Inspect the editable grading policy.")
    policy_sub = p_policy.add_subparsers(dest="policy_command", required=True)
    policy_sub.add_parser("show", help="Print the current grading policy as JSON.").set_defaults(
        func=_cmd_policy_show
    )
    policy_sub.add_parser("path", help="Print the settings.json path.").set_defaults(
        func=_cmd_policy_path
    )
    policy_sub.add_parser("validate", help="Validate the current grading policy.").set_defaults(
        func=_cmd_policy_validate
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = args.func  # set by every leaf subcommand
    result: int = func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
