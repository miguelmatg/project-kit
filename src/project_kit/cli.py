"""Command-line entry point."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from project_kit import (
    __version__,
    agents,
    approval,
    backlog,
    doctor,
    handoff,
    installer,
    provision,
)
from project_kit import (
    help as help_guide,
)
from project_kit.config import (
    PROVIDERS,
    Config,
    ConfigError,
    config_path,
    load_config,
    save_config,
)
from project_kit.gh import Gh, GhError
from project_kit.providers.github import GitHubProvider
from project_kit.state import PHASES, StateError, load_state
from project_kit.templating import TemplateError
from project_kit.workflow import WorkflowError, default_workflow, load_workflow, render_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-kit",
        description="Define, plan and set up a project before handing off to Spec Kit.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="check that the required tools are available")

    init = sub.add_parser(
        "init",
        help="install project-kit into the current directory (never overwrites existing files)",
    )
    init.add_argument(
        "--here", action="store_true", help="accepted for compatibility; init always installs here"
    )
    init.add_argument("--project-name", help="project name (default: the directory name)")
    init.add_argument("--provider", choices=PROVIDERS, default="github")
    init.add_argument("--language", default="en", help="language of the generated documents")
    init.add_argument(
        "--ai-coauthor",
        choices=("keep", "remove"),
        help="whether AI assistants appear as co-authors of commits and PRs "
        "(asked when omitted and a terminal is attached)",
    )

    init.add_argument(
        "--agent",
        choices=(*agents.AGENT_IDS, "none"),
        help="AI agent to open when init finishes, or none (asked when omitted and a terminal "
        "is attached)",
    )

    sub.add_parser("status", help="show the phases of the project and what comes next")
    sub.add_parser("help", help="show a visual guide to the flow and the commands")

    bl = sub.add_parser("backlog", help="work with .project-kit/backlog.json")
    bl_sub = bl.add_subparsers(dest="backlog_command", required=True)
    bl_sub.add_parser("validate", help="validate the backlog and print a summary")

    pv = sub.add_parser(
        "provision",
        help="create milestones, labels and branches on GitHub from the backlog",
    )
    pv.add_argument("--repo", help="owner/name (default: the repository of the current directory)")
    pv.add_argument(
        "--project",
        help="GitHub Project to use: its number or exact title, or a new title to create "
        "(default: detect the ones linked to the repository)",
    )
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
    for note in report.notes:
        print(f"\nNote: {note}")
    if not report.created:
        print("\nNothing to do: project-kit is already installed here.")


NEXT_AFTER_INIT = """
Next: open Claude Code in this directory (restart it if it was already open, so it loads
the new skills) and run /pk-start. It asks whether to stop here or to start defining the
project. `project-kit status` shows where you are at any time."""


def _status() -> int:
    root = Path.cwd()
    try:
        config = load_config(root)
        print(render_status(load_workflow(root), load_state(root), config.project_name))
    except (ConfigError, StateError, WorkflowError) as exc:
        print(f"project-kit status: {exc}", file=sys.stderr)
        return 1
    return 0


def _offer_agent(root: Path, requested: str | None) -> bool:
    """List the supported AI agents and open the chosen one with /pk-start.

    Returns True when an agent was started, so the caller does not repeat the instructions.
    """
    if requested == "none":
        return False
    if requested is None and not sys.stdin.isatty():
        return False  # nobody to ask, and nothing must start by surprise
    for known in agents.AGENTS:
        if agents.is_inside(known):
            print(f"\nYou are already inside {known.name}: run {known.prompt} here.")
            return True
    agent = agents.get_agent(requested) if requested else agents.choose()
    if agent is None:
        return False
    if agents.find_executable(agent) is None:
        print(f"\n{agent.name} was not found on your PATH. Install it from {agent.install_hint}.")
        return False
    try:
        config = load_config(root)
        if config.agent != agent.id:
            config.agent = agent.id
            save_config(root, config)
    except ConfigError as exc:
        print(f"project-kit init: {exc}", file=sys.stderr)
        return False
    print(f"\nStarting {agent.name} with {agent.prompt}...\n")
    agents.launch(agent, root)
    return True


def _help() -> int:
    root = Path.cwd()
    workflow, state, name = default_workflow(), None, None
    try:
        name = load_config(root).project_name
        workflow, state = load_workflow(root), load_state(root)
    except (ConfigError, StateError, WorkflowError):
        workflow, state, name = default_workflow(), None, None  # not a project here: generic guide
    print(help_guide.render_help(workflow, state, name, help_guide.Style.detect()))
    return 0


def _init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    choice = args.ai_coauthor
    if choice is None and sys.stdin.isatty() and not config_path(root).exists():
        remove = _ask("Remove AI assistants (Claude, Copilot...) as co-authors of commits and PRs?")
        choice = "remove" if remove else "keep"
    config = Config(
        project_name=args.project_name or root.name,
        provider=args.provider,
        language=args.language,
        ai_coauthor=choice != "remove",
    )
    try:
        config.validate()
        report = installer.init_project(root, config)
    except (ConfigError, StateError) as exc:
        print(f"project-kit init: {exc}", file=sys.stderr)
        return 1
    _print_init_report(report)
    if not _offer_agent(root, args.agent):
        print(NEXT_AFTER_INIT)
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
    except (ConfigError, StateError, backlog.BacklogError, WorkflowError) as exc:
        print(f"project-kit approve: {exc}", file=sys.stderr)
        return 1
    print(f"Phase '{phase}' approved.")
    if phase == "handoff":
        for rel in handoff.finish_handoff(Path.cwd()):
            print(f"Removed {rel.as_posix()}: the constitution carries its content now.")
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
            project=args.project,
            interactive=sys.stdin.isatty(),
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


def _utf8_output() -> None:
    """Print UTF-8 whatever the console code page is.

    Without a terminal (a pipe, a tool, a file) Python on Windows encodes with the ANSI code
    page, and the accents of the project's documents come out as replacement characters.
    A real terminal is left alone: it has its own, correct, path.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream.isatty():
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # a stream that cannot be reconfigured keeps what it has


def main(argv: Sequence[str] | None = None) -> int:
    _utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        checks = doctor.run_checks()
        print(doctor.render(checks))
        return doctor.exit_code(checks)
    if args.command == "init":
        return _init(args)
    if args.command == "status":
        return _status()
    if args.command in ("help", None):
        return _help()
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
