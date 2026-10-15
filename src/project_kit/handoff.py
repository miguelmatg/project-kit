"""``project-kit handoff``: hand the project over to Spec Kit.

project-kit never writes inside ``.specify/``; Spec Kit owns it. What this module does:

* detects Spec Kit (CLI and ``.specify/``) and its version;
* generates ``.project-kit/handoff/constitution-input.md``, the text to pass to
  ``/speckit-constitution``;
* with explicit confirmation, installs the Spec Kit CLI and initialises the repository by
  running Spec Kit's own commands.

The only contract with Spec Kit is therefore a plain file plus its public commands, so an
unknown Spec Kit version degrades to a warning instead of breaking.
"""

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from project_kit.backlog import BacklogError, load_backlog
from project_kit.config import PROJECT_DIR, Config, load_config
from project_kit.fsutil import atomic_write_text
from project_kit.state import State, load_state
from project_kit.templating import render

# Spec Kit versions (major.minor) this release was tried against.
TESTED_SPECKIT = ("1.2",)
MANAGED_HEADER = "<!-- project-kit:managed -->"
TEMPLATE = "constitution-input.md"
INPUT_FILE = Path(PROJECT_DIR) / "handoff" / "constitution-input.md"
EXTRA_FILE = Path(PROJECT_DIR) / "handoff" / "constitution-extra.md"
CONSTITUTION = Path(".specify") / "memory" / "constitution.md"
# Spec Kit's empty template is full of [UPPER_CASE_PLACEHOLDERS]; a written constitution has none.
_PLACEHOLDER = re.compile(r"\[[A-Z][A-Z0-9_]{3,}\]")

Which = Callable[[str], str | None]
Runner = Callable[..., subprocess.CompletedProcess]


# --- detecting Spec Kit ------------------------------------------------------------------


@dataclass(frozen=True)
class SpecKit:
    cli: str | None  # path of the `specify` executable
    cli_version: str | None
    initialised: bool  # this repository has a .specify/ directory
    project_version: str | None  # version recorded by Spec Kit in .specify/init-options.json

    @property
    def installed(self) -> bool:
        return self.cli is not None


def is_tested(version: str | None) -> bool:
    return bool(version) and any(
        version == t or version.startswith(t + ".")
        for t in TESTED_SPECKIT  # type: ignore[union-attr]
    )


def _cli_version(exe: str, runner: Runner) -> str | None:
    try:
        proc = runner([exe, "--version"], capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"\d+\.\d+\.\d+\S*", proc.stdout or "") if proc.returncode == 0 else None
    return match.group(0) if match else None


def _project_version(root: Path) -> str | None:
    try:
        data = json.loads((root / ".specify" / "init-options.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = data.get("speckit_version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else None


def detect_speckit(
    root: Path, which: Which = shutil.which, runner: Runner = subprocess.run
) -> SpecKit:
    cli = which("specify")
    return SpecKit(
        cli=cli,
        cli_version=_cli_version(cli, runner) if cli else None,
        initialised=(root / ".specify").is_dir(),
        project_version=_project_version(root),
    )


# --- the constitution input --------------------------------------------------------------


def _load_template(root: Path) -> str:
    """The project's own copy if it has one (templates are overridable), else the shipped one."""
    own = root / PROJECT_DIR / "templates" / TEMPLATE
    if own.is_file():
        return own.read_text(encoding="utf-8")
    return (files("project_kit") / "assets" / "templates" / TEMPLATE).read_text(encoding="utf-8")


def _adr_entry(path: Path, root: Path) -> str:
    text = path.read_text(encoding="utf-8")
    title = next(
        (m.group(1).strip() for line in text.splitlines() if (m := re.match(r"#\s+(.+)", line))),
        path.stem,
    )
    # "Status: Accepted", "**Status:** Accepted", "- Status: Accepted"...
    status = re.search(
        r"^[\s*_#>\-]*status[\s*_]*[:\-][\s*_]*([A-Za-z]+)", text, re.IGNORECASE | re.MULTILINE
    )
    label = f" ({status.group(1)})" if status else ""
    return f"- `{path.relative_to(root).as_posix()}`: {title}{label}"


def list_decisions(root: Path) -> list[str]:
    adr_dir = root / "docs" / "adr"
    if not adr_dir.is_dir():
        return []
    return [_adr_entry(p, root) for p in sorted(adr_dir.glob("*.md"))]


def _references(root: Path) -> str:
    lines = []
    docs = [
        f"`{p}`"
        for p in ("docs/project/brief.md", "docs/project/roadmap.md")
        if (root / p).is_file()
    ]
    if docs:
        lines.append(f"- Project documents: {', '.join(docs)}.")
    try:
        phases = [p.title for p in load_backlog(root).phases]
    except BacklogError:
        phases = []
    if phases:
        lines.append(f"- Delivery phases: {', '.join(phases)}.")
    return "\n".join(lines)


_MERGE_WORDS = {"squash": "squash merge", "merge": "merge commit", "rebase": "rebase merge"}


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def merge_summary(config: Config) -> str:
    """ "Squash merge into `develop`; merge commit into `release` and `main`." from the config."""
    groups: dict[str, list[str]] = {}
    for key in ("develop", "release", "main"):
        groups.setdefault(config.merge[key], []).append(f"`{config.branches[key]}`")
    parts = [f"{_MERGE_WORDS[how]} into {_join(names)}" for how, names in groups.items()]
    text = "; ".join(parts) + "."
    return text[0].upper() + text[1:]


def rules_index(root: Path, state: State) -> str:
    """Where each kind of rule lives, only for the sources this project actually has."""
    lines = []

    def has(path: str) -> bool:
        return (root / path).is_file()

    title = state.get_id("project", "title")
    number = state.get_id("project", "number")
    if title or number:
        url = state.get_id("project", "url")
        board = f'the GitHub Project "{title}"' if title else f"GitHub Project #{number}"
        board += f" ({url})" if url else ""
        lines.append(
            f"- **Tasks and tracking**: {board} and the repository issues are the source of "
            "truth for the work. One issue is one spec, and the spec's pull request closes it "
            "(`Closes #N`). Do not keep a parallel task list: a spec's `tasks.md` details its "
            "steps, while progress is tracked on its issue and card. Move the card to In "
            "progress when the spec starts, to In review with the pull request and to Done when "
            "it is merged."
        )
    if has(".project-kit/backlog.json"):
        lines.append(
            "- **Backlog**: `.project-kit/backlog.json` is the plan the issues were created "
            "from. New work is added there and provisioned, not invented in a spec."
        )
    if has("docs/project/brief.md"):
        lines.append(
            "- **Scope and goals**: `docs/project/brief.md`. A spec outside the brief's scope "
            "needs the brief amended first."
        )
    if has("docs/project/roadmap.md"):
        lines.append("- **Roadmap and phases**: `docs/project/roadmap.md`.")
    if (root / "docs" / "adr").is_dir():
        lines.append(
            "- **Technical decisions**: `docs/adr/`, listed above. A spec follows them; a "
            "change of course is a new ADR, not a silent deviation."
        )
    if has("docs/development-workflow.md"):
        lines.append(
            "- **Development process**: `docs/development-workflow.md` (branches, reviews, "
            "commits, quality gates and Definition of Done). This constitution summarises it; "
            "keep both in agreement."
        )
    templates = [
        what
        for path, what in (
            (".github/pull_request_template.md", "the pull request template"),
            (".github/ISSUE_TEMPLATE/feature.yml", "the issue templates"),
        )
        if has(path)
    ]
    if templates:
        lines.append(f"- **Templates**: use {_join(templates)} in `.github/`.")
    return "\n".join(lines) if lines else "No project documents are recorded yet."


def build_constitution_input(root: Path, config: Config) -> str:
    decisions = list_decisions(root)
    extra_path = root / EXTRA_FILE
    extra = ""
    if extra_path.is_file() and extra_path.read_text(encoding="utf-8").strip():
        extra = (
            "\n## Project-specific rules\n\n"
            + extra_path.read_text(encoding="utf-8").strip()
            + "\n"
        )
    variables = {
        "project_name": config.project_name,
        "language": config.language,
        "provider": config.provider,
        **{f"branches.{k}": v for k, v in config.branches.items()},
        "stack": (
            "defined by the decisions on record below."
            if decisions
            else "not decided yet; it is settled by an ADR before the first spec."
        ),
        "spec_branch": config.spec_branch,
        "merge_summary": merge_summary(config),
        "rules_index": rules_index(root, load_state(root)),
        "references": _references(root),
        "decisions": "\n".join(decisions) if decisions else "No decisions are recorded yet.",
        "extra": extra,
    }
    return render(_load_template(root), variables)


def write_managed(path: Path, text: str) -> str:
    """Write a generated file. Returns created | updated | unchanged | kept.

    A file that lost its ``project-kit:managed`` header has been taken over by the user and
    is never overwritten.
    """
    if not path.exists():
        atomic_write_text(path, text)
        return "created"
    current = path.read_text(encoding="utf-8")
    if current == text:
        return "unchanged"
    if MANAGED_HEADER not in current.splitlines()[:3]:
        return "kept"
    atomic_write_text(path, text)
    return "updated"


# --- the temporary files ------------------------------------------------------------------


def constitution_ready(root: Path) -> bool:
    """True once ``/speckit-constitution`` has replaced Spec Kit's template with real text."""
    try:
        text = (root / CONSTITUTION).read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(text.strip()) and not _PLACEHOLDER.search(text)


def finish_handoff(root: Path) -> list[Path]:
    """Delete the handoff files, now that the constitution carries their content.

    The input and the extra rules only exist to feed ``/speckit-constitution``; from then on
    the constitution is the one source, and Spec Kit owns it. Returns what was removed.
    """
    removed = []
    for rel in (INPUT_FILE, EXTRA_FILE):
        path = root / rel
        if path.is_file():
            path.unlink()
            removed.append(rel)
    return removed


# --- installing Spec Kit -----------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    description: str
    command: list[str]


def install_steps(sk: SpecKit, which: Which) -> tuple[list[Step], list[str]]:
    """What has to run to get a working Spec Kit here, and what prevents it."""
    steps: list[Step] = []
    problems: list[str] = []
    if not sk.installed:
        if which("uv"):
            steps.append(Step("Install the Spec Kit CLI", ["uv", "tool", "install", "specify-cli"]))
        else:
            problems.append(
                "uv is needed to install Spec Kit (https://docs.astral.sh/uv/), or install "
                "the `specify-cli` package yourself (for example with pipx) and run this again."
            )
    if not sk.initialised:
        steps.append(
            Step(
                "Initialise Spec Kit in this repository (it merges its files into it)",
                [
                    "specify",
                    "init",
                    "--here",
                    "--integration",
                    "claude",
                    "--force",
                    "--non-interactive",
                ],
            )
        )
    return steps, problems


def _resolve_specify(which: Which, runner: Runner) -> str | None:
    """Find ``specify`` right after installing it, when the current PATH may not have it yet."""
    if found := which("specify"):
        return found
    try:
        proc = runner(
            ["uv", "tool", "dir", "--bin"], capture_output=True, text=True, encoding="utf-8"
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    bin_dir = Path((proc.stdout or "").strip())
    for name in ("specify.exe", "specify"):
        if (bin_dir / name).is_file():
            return str(bin_dir / name)
    return None


# --- the command -------------------------------------------------------------------------

NEXT_STEPS = f"""\
Next steps
  1. In Claude Code, run:
       /speckit-constitution @{INPUT_FILE.as_posix()}
     Spec Kit owns .specify/memory/constitution.md; project-kit never edits it. The input
     carries the project's rules and an index of where each kind of rule lives.
  2. Optional: mention docs/project/ and docs/adr/ in CLAUDE.md or AGENTS.md so that
     /speckit-specify and /speckit-plan read them.
  3. Every card of the backlog is a candidate spec: use its issue as the input of
     /speckit-specify.
  4. When the constitution is written, run: project-kit approve handoff
     It deletes the input (and the extra rules), which are only needed until then."""


def run_handoff(
    root: Path,
    *,
    install: bool,
    assume_yes: bool,
    dry_run: bool,
    confirm: Callable[[str], bool],
    out: Callable[[str], None] = print,
    which: Which = shutil.which,
    runner: Runner = subprocess.run,
) -> int:
    """Returns the process exit code."""
    config = load_config(root)
    state = load_state(root)
    if not state.is_approved("plan"):
        out("Note: the plan has not been approved yet (project-kit approve plan).\n")

    sk = detect_speckit(root, which, runner)
    text = build_constitution_input(root, config)
    target = root / INPUT_FILE

    if state.is_approved("handoff") and constitution_ready(root):
        out(
            "The handoff is already done: the constitution is in place and the input file was "
            "removed. To change the rules, amend the constitution with /speckit-constitution."
        )
        return 0

    if dry_run:
        out(f"Dry run: {INPUT_FILE.as_posix()} would contain:\n\n{text}")
    else:
        result = write_managed(target, text)
        if result == "kept":
            out(
                f"{INPUT_FILE.as_posix()} no longer has the project-kit:managed header, so it was "
                "left as it is. Delete it to have it generated again."
            )
        else:
            out(f"{INPUT_FILE.as_posix()}: {result}.")

    for note in _speckit_notes(sk):
        out(note)
    if note := _stale_template_note(root):
        out(note)

    steps, problems = install_steps(sk, which)
    if steps and not install:
        out(
            "\nSpec Kit is not ready in this repository. Run `project-kit handoff "
            "--install-speckit` to set it up, or do it yourself with Spec Kit's own commands."
        )
    elif steps:
        for problem in problems:
            out(f"\nBLOCKING: {problem}")
        if problems:
            return 1
        out("\nTo set up Spec Kit:")
        for step in steps:
            out(f"  - {step.description}: {' '.join(step.command)}")
        if dry_run:
            out("\nDry run: nothing was run.")
            return 0
        if not assume_yes and not confirm("\nRun these commands?"):
            out("Aborted. Spec Kit was not touched.")
            return 1
        if not _run_steps(root, steps, out, which, runner):
            return 1
        sk = detect_speckit(root, which, runner)
    elif problems:
        for problem in problems:
            out(f"\nBLOCKING: {problem}")
        return 1

    if sk.initialised and not dry_run:
        out("\n" + NEXT_STEPS)
    return 0


def _stale_template_note(root: Path) -> str | None:
    """The project's own copy wins over the shipped one, so an old copy hides what is new."""
    own = root / PROJECT_DIR / "templates" / TEMPLATE
    if not own.is_file() or "{{rules_index}}" in own.read_text(encoding="utf-8"):
        return None
    return (
        f"Note: {own.relative_to(root).as_posix()} comes from an older project-kit and lacks "
        "the index of the project's rules and the branch settings. Run `project-kit upgrade` "
        "to see how to bring it up to date, or add `{{rules_index}}`, `{{spec_branch}}` and "
        "`{{merge_summary}}` to your copy."
    )


def _speckit_notes(sk: SpecKit) -> list[str]:
    notes = []
    for label, version in (("CLI", sk.cli_version), ("this repository", sk.project_version)):
        if version and not is_tested(version):
            notes.append(
                f"Note: Spec Kit {label} is version {version}, but project-kit was tried with "
                f"{', '.join(v + '.x' for v in TESTED_SPECKIT)}. Only the constitution input "
                "file is relied on, so this should still work."
            )
    return notes


def _run_steps(
    root: Path, steps: list[Step], out: Callable[[str], None], which: Which, runner: Runner
) -> bool:
    for step in steps:
        command = list(step.command)
        if command[0] == "specify":
            exe = _resolve_specify(which, runner)
            if exe is None:
                out(
                    "\nSpec Kit was installed but `specify` is not on your PATH yet. Run "
                    "`uv tool update-shell`, open a new terminal and run this command again."
                )
                return False
            command[0] = exe
        out(f"\n> {' '.join(command)}")
        proc = runner(command, cwd=root)
        if proc.returncode != 0:
            out(f"\nStopped: `{' '.join(step.command)}` failed (exit {proc.returncode}).")
            return False
    return True
