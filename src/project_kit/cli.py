"""Command-line entry point."""

import argparse
from collections.abc import Sequence

from project_kit import __version__, doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-kit",
        description="Define, plan and set up a project before handing off to Spec Kit.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="check that the required tools are available")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        checks = doctor.run_checks()
        print(doctor.render(checks))
        return doctor.exit_code(checks)
    parser.print_help()
    return 0
