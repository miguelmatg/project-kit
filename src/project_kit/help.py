"""``project-kit help``: a visual guide to the flow and the commands, for the terminal.

Plain text with a little ANSI colour. It degrades on its own: no colour when the output is not
a terminal or ``NO_COLOR`` is set, and ASCII instead of box-drawing characters when the output
encoding cannot print them (the Windows console redirected to a file, for instance).
"""

import os
import shutil
import sys
import textwrap
from dataclasses import dataclass
from typing import TextIO

from project_kit import __version__
from project_kit.state import State
from project_kit.workflow import Workflow, step_marks

# What runs in the terminal. The test suite checks that every subcommand is listed here.
TERMINAL_COMMANDS = (
    ("project-kit init", "install the skills, templates and workflow in this directory"),
    ("project-kit status", "show the phases, where you are and what comes next"),
    ("project-kit doctor", "check that git, gh, uv and Spec Kit are available"),
    ("project-kit upgrade [--apply]", "update the skills and templates a project already has"),
    ("project-kit approve <phase>", "record your sign-off of a phase"),
    ("project-kit backlog validate", "check .project-kit/backlog.json"),
    ("project-kit provision [--dry-run]", "create milestones, branches, Project, issues"),
    ("project-kit handoff [--install-speckit]", "prepare the Spec Kit constitution input"),
    ("project-kit help", "show this guide"),
)


@dataclass(frozen=True)
class Style:
    color: bool = False
    unicode: bool = False

    @classmethod
    def detect(cls, stream: TextIO | None = None) -> "Style":
        stream = stream or sys.stdout
        color = bool(getattr(stream, "isatty", lambda: False)()) and not os.environ.get("NO_COLOR")
        try:
            "─│→".encode(getattr(stream, "encoding", None) or "ascii")
            unicode = True
        except (UnicodeEncodeError, LookupError):
            unicode = False
        if color and os.name == "nt":
            os.system("")  # switches the Windows console to understand ANSI escapes
        return cls(color=color, unicode=unicode)

    def paint(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def bold(self, text: str) -> str:
        return self.paint(text, "1")

    def dim(self, text: str) -> str:
        return self.paint(text, "2")

    def green(self, text: str) -> str:
        return self.paint(text, "32")

    def cyan(self, text: str) -> str:
        return self.paint(text, "1;36")

    @property
    def bar(self) -> str:
        return "│" if self.unicode else "|"

    @property
    def arrow(self) -> str:
        return "→" if self.unicode else "->"

    def rule(self, title: str, width: int) -> str:
        line = ("─" if self.unicode else "-") * max(width - len(title) - 2, 4)
        return f"{self.bold(title)} {self.dim(line)}"


def _mark(style: Style, mark: str) -> str:
    cell = f"[{mark}]"
    if mark == "x":
        return style.green(cell)
    if mark == ">":
        return style.cyan(cell)
    return style.dim(cell) if mark == "-" else cell


def _flow(workflow: Workflow, state: State | None, style: Style, width: int) -> list[str]:
    marks = (
        step_marks(workflow, state)
        if state is not None
        else [(s, " " if s.enabled else "-", "") for s in workflow.steps]
    )
    indent = " " * 18
    lines = []
    for n, (step, mark, _note) in enumerate(marks):
        name = f"{step.id:<10} /{step.skill}"
        lines.append(f"  {_mark(style, mark)} {style.bold(name) if mark == '>' else name}")
        detail = textwrap.wrap(step.title, max(width - len(indent) - 4, 30))
        if step.produces:
            detail.append(f"{style.arrow} {', '.join(step.produces)}")
        for text in detail:
            lines.append(f"   {style.bar}{indent[5:]}{style.dim(text)}")
        if n < len(marks) - 1:
            lines.append(f"   {style.bar}")
    return lines


def render_help(
    workflow: Workflow,
    state: State | None = None,
    project_name: str | None = None,
    style: Style | None = None,
    width: int | None = None,
) -> str:
    """The guide. With a ``state`` it marks the progress of the project in this directory."""
    style = style or Style()
    width = min(width or shutil.get_terminal_size((80, 24)).columns, 100)
    out = [
        f"{style.bold('project-kit')} {__version__}",
        "Define, plan and set up a project before handing it over to Spec Kit.",
        "",
        style.rule("HOW IT WORKS", width),
        "  The terminal sets things up; your AI agent (Claude Code) runs the guided",
        "  conversations as /pk-... skills. Every phase ends with your approval, and",
        "  you can fill each document by hand instead.",
        "",
    ]
    title = "THE FLOW" + (f"  ({project_name})" if project_name else "")
    out += [style.rule(title, width), *_flow(workflow, state, style, width), ""]
    if state is not None:
        nxt = workflow.next_step(state)
        if nxt is None:
            out += ["Every enabled phase is done.", ""]
        else:
            out += [
                f"Next: {style.cyan('/' + nxt.skill)} in your agent (or see `project-kit status`).",
                "",
            ]
    out += [style.rule("IN THE TERMINAL", width)]
    for cmd, desc in TERMINAL_COMMANDS:
        out += [f"  {style.bold(cmd)}", f"      {style.dim(desc)}"]
    out += [""]
    if state is None:
        out += [
            style.rule("FIRST TIME", width),
            "  1. project-kit doctor    check the tools",
            "  2. project-kit init      in your repository; it offers to open your agent",
            "  3. /pk-start             in the agent: only initialise, or begin",
            "",
        ]
    out += ["Details of one command: project-kit <command> --help"]
    return "\n".join(out)
