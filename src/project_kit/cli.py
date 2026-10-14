"""Command-line entry point."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from project_kit import __version__, doctor, installer
from project_kit.config import PROVIDERS, Config, ConfigError
from project_kit.state import StateError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-kit",
        description="Define, plan and set up a project before handing off to Spec Kit.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="check that the required tools are available")

    init = sub.add_parser(
        "init", help="install project-kit into a repository (never overwrites existing files)"
    )
    init.add_argument("--here", action="store_true", help="install into the current directory")
    init.add_argument("--project-name", help="project name (default: the directory name)")
    init.add_argument("--provider", choices=PROVIDERS, default="github")
    init.add_argument("--language", default="en", help="language of the generated documents")
    return parser


def _print_init_report(report: installer.Report) -> None:
    for label, paths in (
        ("created", report.created),
        ("kept (differs from the shipped version)", report.kept),
        ("already up to date", report.unchanged),
    ):
        if paths:
            print(f"{label}:")
            for path in paths:
                print(f"  {path.as_posix()}")
    if not report.created:
        print("\nNothing to do: project-kit is already installed here.")


def _init(args: argparse.Namespace) -> int:
    if not args.here:
        print(
            "project-kit init: pass --here to install into the current directory.", file=sys.stderr
        )
        return 2
    root = Path.cwd()
    config = Config(
        project_name=args.project_name or root.name,
        provider=args.provider,
        language=args.language,
    )
    try:
        config.validate()
        report = installer.init_project(root, config)
    except (ConfigError, StateError) as exc:
        print(f"project-kit init: {exc}", file=sys.stderr)
        return 1
    _print_init_report(report)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        checks = doctor.run_checks()
        print(doctor.render(checks))
        return doctor.exit_code(checks)
    if args.command == "init":
        return _init(args)
    parser.print_help()
    return 0
