"""``vpat-review`` command-line interface.

Library-first: this is a thin adapter over the package. Today it exposes the
editable grading policy (inspect / validate / where it's stored). The full
``review`` pipeline is wired in Phase 6 once the service layer lands.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from vpat_reviewer import __version__
from vpat_reviewer.config import settings


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


def _cmd_review(_args: argparse.Namespace) -> int:
    print(
        "The `review` command is wired in Phase 6 (service orchestration).\n"
        "Until then, use the legacy entry points (run_app.py / make_demo.py).",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vpat-review", description="VPAT accessibility reviewer.")
    parser.add_argument("--version", action="version", version=f"vpat-review {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_review = sub.add_parser("review", help="Generate a compliance report from a VPAT (Phase 6).")
    p_review.add_argument("input", help="Path to the vendor VPAT (PDF/DOCX/TXT).")
    p_review.add_argument("-o", "--output", help="Output PDF path.")
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
