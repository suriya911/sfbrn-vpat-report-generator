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

from vpat_reviewer import __version__, audit, service
from vpat_reviewer.config import policy_form, settings
from vpat_reviewer.config.settings import IDENTITY_DEFAULTS
from vpat_reviewer.domain.models import DocumentKind
from vpat_reviewer.domain.policy import GradingPolicy

# Distinguish "this is the wrong kind of file" from "this is a VPAT we could not
# read" -- a caller scripting the CLI should be able to tell them apart.
EXIT_UNPARSEABLE = 1
EXIT_WRONG_DOCUMENT = 2

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
        print(json.dumps(service.to_dict(result), indent=2, ensure_ascii=False))
    else:
        _print_summary(result)


def _wrong_document(result: service.ReviewResult) -> str:
    """Why this file should not be scored at all, or "" if it is fine to score.

    Distinct from "a VPAT we could not parse": scoring a remediation plan or a
    blank template yields an authoritative-looking number that means nothing, so
    it is worth refusing loudly rather than reporting 0%.
    """
    doc = result.document
    if doc.document_kind in (DocumentKind.VPAT, DocumentKind.UNKNOWN):
        return ""
    reasons = "; ".join(doc.document_kind_reasons)
    return f"{doc.document_kind.value}: {reasons}" if reasons else doc.document_kind.value


def _cmd_analyze(args: argparse.Namespace) -> int:
    result = service.analyze(args.input, answers=_answers(args))
    _emit(result, args.json)
    wrong = _wrong_document(result)
    if wrong:
        print(f"This file does not look like a VPAT — {wrong}", file=sys.stderr)
        return EXIT_WRONG_DOCUMENT
    return 0 if result.has_criteria else EXIT_UNPARSEABLE


def _default_output(input_path: str) -> str:
    p = Path(input_path)
    return str(p.with_name(f"{p.stem} - VPAT Report.pdf"))


def _cmd_review(args: argparse.Namespace) -> int:
    result = service.analyze(args.input, answers=_answers(args))
    wrong = _wrong_document(result)
    if wrong:
        _emit(result, args.json)
        print(f"Refusing to report on this file — {wrong}", file=sys.stderr)
        return EXIT_WRONG_DOCUMENT
    if not result.has_criteria:
        _emit(result, args.json)
        print("Nothing to report — no criteria were parsed.", file=sys.stderr)
        return EXIT_UNPARSEABLE
    output = args.output or _default_output(args.input)
    # --style overrides the saved setting for this run only; it is layered onto a
    # copy of the settings so nothing is written back to settings.json.
    render_settings = None
    if args.style:
        render_settings = dict(settings.load_settings())
        render_settings["report_style"] = args.style.replace("-", "_")
    service.render_result(result, output, logo_path=args.logo or "", settings=render_settings)
    if not args.no_json:
        service.write_json(result, args.json_out or str(Path(output).with_suffix(".json")))
    if not args.no_log:
        _record_audit(result, args, render_settings)
    _emit(result, args.json)
    return 0


def _record_audit(
    result: service.ReviewResult,
    args: argparse.Namespace,
    render_settings: dict[str, Any] | None,
) -> None:
    """Append this run to the audit log, if the settings ask for one.

    The CLI is a composition root, so it -- not service -- decides that a log
    happens at all, the same way it decides no assessor runs here.

    ``verdict_source`` is "offline" and not left empty precisely *because* the
    CLI never calls Bedrock (§5): a row from this path is always the
    deterministic classifier's, and saying so is the point of the column.
    """
    log = audit.log_for(render_settings or settings.load_settings())
    if log is None:
        return
    log.record(
        service.build_audit_event(
            result,
            source_path=args.input,
            settings=render_settings or settings.load_settings(),
            verdict_source="offline" if result.verdict else "",
        )
    )


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


def _cmd_policy_set(args: argparse.Namespace) -> int:
    new, err = policy_form.set_field(settings.load_policy(), args.key, args.value)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    settings.save_policy(new)
    print(f"Set {args.key}. Saved to {settings.default_settings_path()}")
    return 0


def _cmd_policy_reset(_args: argparse.Namespace) -> int:
    settings.save_policy(GradingPolicy.default())
    print("Grading policy reset to defaults.")
    return 0


def _cmd_policy_import(args: argparse.Namespace) -> int:
    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"error: could not read {args.file}: {e}", file=sys.stderr)
        return 1
    policy = GradingPolicy.from_dict(data)
    problems = policy.validate()
    if problems:
        print("error: invalid policy:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    settings.save_policy(policy)
    print("Imported grading policy.")
    return 0


def _cmd_settings_show(_args: argparse.Namespace) -> int:
    print(json.dumps(settings.load_settings(), indent=2, ensure_ascii=False))
    return 0


def _cmd_settings_set(args: argparse.Namespace) -> int:
    if args.key not in IDENTITY_DEFAULTS:
        known = ", ".join(IDENTITY_DEFAULTS)
        print(f"error: unknown setting '{args.key}'. Known: {known}", file=sys.stderr)
        return 1
    settings.save_settings({args.key: args.value})
    print(f"Set {args.key}.")
    return 0


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
    p_review.add_argument(
        "--json-out", help="Where to write the machine-readable record (default: beside the PDF)."
    )
    p_review.add_argument(
        "--no-json", action="store_true", help="Do not write the JSON record beside the report."
    )
    p_review.add_argument(
        "--no-log", action="store_true", help="Do not append this run to the CSV audit log."
    )
    p_review.add_argument(
        "--style",
        choices=["full", "one-page"],
        help="Report style for this run, overriding the saved report_style setting.",
    )
    _add_impact_flags(p_review)
    p_review.set_defaults(func=_cmd_review)

    p_policy = sub.add_parser("policy", help="Inspect and edit the grading policy.")
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
    p_set = policy_sub.add_parser(
        "set", help="Set one policy field (e.g. compliance_threshold 85)."
    )
    p_set.add_argument("key", help="Field name, e.g. graded_level, compliance_threshold.")
    p_set.add_argument("value", help="New value (comma-separate lists).")
    p_set.set_defaults(func=_cmd_policy_set)
    policy_sub.add_parser("reset", help="Reset the grading policy to defaults.").set_defaults(
        func=_cmd_policy_reset
    )
    p_import = policy_sub.add_parser("import", help="Load a full policy from a JSON file.")
    p_import.add_argument("file", help="Path to a policy JSON file (see `policy show`).")
    p_import.set_defaults(func=_cmd_policy_import)

    p_settings = sub.add_parser("settings", help="Inspect and edit organization settings.")
    settings_sub = p_settings.add_subparsers(dest="settings_command", required=True)
    settings_sub.add_parser("show", help="Print organization settings as JSON.").set_defaults(
        func=_cmd_settings_show
    )
    p_sset = settings_sub.add_parser("set", help="Set one setting (e.g. org_name 'Acme').")
    p_sset.add_argument("key", help="Setting name, e.g. org_name, reviewer_name, threshold.")
    p_sset.add_argument("value", help="New value.")
    p_sset.set_defaults(func=_cmd_settings_set)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = args.func  # set by every leaf subcommand
    result: int = func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
