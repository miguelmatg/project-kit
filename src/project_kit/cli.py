"""Command-line entry point."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from project_kit import __version__, approval, backlog, doctor, handoff, installer, provision
from project_kit.config import PROVIDERS, Config, ConfigError
from project_kit.gh import Gh, GhError
from project_kit.providers.github import GitHubProvider
from project_kit.state import PHASES, StateError
from project_kit.templating import TemplateError


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

    bl = sub.add_parser("backlog", help="work with .project-kit/backlog.json")
    bl_sub = bl.add_subparsers(dest="backlog_command", required=True)
    bl_sub.add_parser("validate", help="validate the backlog and print a summary")

    pv = sub.add_parser(
        "provision",
        help="create milestones, labels and branches on GitHub from the backlog",
    )
    pv.add_argument("--repo", help="owner/name (default: the repository of the current directory)")
    pv.add_argument("--dry-run", action="store_true", help="show the plan and change nothing")
    pv.add_argument("--yes", action="store_true", help="do not ask for confirmation")

    ho = sub.add_parser(
        "handoff", help="generate the constitution input and hand the project over to Spec Kit"
    )
    ho.add_argument(
        "--install-speckit",
        action="store_true",
        help="install the Spec Kit CLI and initialise this repository, after confirmation",
    )
    ho.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    ho.add_argument("--yes", action="store_true", help="do not ask for confirmation")

    ap = sub.add_parser("approve", help="record the user's approval of a phase")
    ap.add_argument("phase", choices=PHASES)
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


def _backlog_validate() -> int:
    try:
        loaded = backlog.load_backlog(Path.cwd())
    except backlog.BacklogError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("Backlog is valid.\n" + loaded.summary())
    return 0


def _approve(phase: str) -> int:
    try:
        approval.approve_phase(Path.cwd(), phase)
    except (ConfigError, StateError, backlog.BacklogError) as exc:
        print(f"project-kit approve: {exc}", file=sys.stderr)
        return 1
    print(f"Phase '{phase}' approved.")
    return 0


def _ask(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:  # no terminal attached: never assume consent
        return False


def _provision(args: argparse.Namespace) -> int:
    try:
        return provision.run_provision(
            Path.cwd(),
            GitHubProvider(Gh(), args.repo),
            dry_run=args.dry_run,
            assume_yes=args.yes,
            confirm=_ask,
        )
    except (ConfigError, StateError, backlog.BacklogError, GhError) as exc:
        print(f"project-kit provision: {exc}", file=sys.stderr)
        return 1


def _handoff(args: argparse.Namespace) -> int:
    try:
        return handoff.run_handoff(
            Path.cwd(),
            install=args.install_speckit,
            assume_yes=args.yes,
            dry_run=args.dry_run,
            confirm=_ask,
        )
    except (ConfigError, StateError, TemplateError) as exc:
        print(f"project-kit handoff: {exc}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        checks = doctor.run_checks()
        print(doctor.render(checks))
        return doctor.exit_code(checks)
    if args.command == "init":
        return _init(args)
    if args.command == "backlog":
        return _backlog_validate()
    if args.command == "provision":
        return _provision(args)
    if args.command == "handoff":
        return _handoff(args)
    if args.command == "approve":
        return _approve(args.phase)
    parser.print_help()
    return 0
