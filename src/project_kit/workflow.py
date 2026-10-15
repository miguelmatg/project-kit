""".project-kit/workflow.yml: the ordered phases of the project-definition flow.

Modelled on Spec Kit's ``workflow.yml``: a list of steps, each one with an optional review
gate. The skills and ``project-kit status`` read it to know what comes next, and
``project-kit approve`` uses it to refuse a gate while an earlier enabled gate is still open.
"""

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from project_kit.config import PROJECT_DIR
from project_kit.state import PHASES, State

SCHEMA_VERSION = "1.0"
_STEP_KEYS = {"id", "title", "skill", "gate", "enabled", "produces"}


class WorkflowError(ValueError):
    """The workflow file is missing, unreadable or invalid."""


def workflow_path(root: Path) -> Path:
    return root / PROJECT_DIR / "workflow.yml"


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    skill: str
    gate: bool = True
    enabled: bool = True
    produces: tuple[str, ...] = ()


@dataclass
class Workflow:
    steps: list[Step] = field(default_factory=list)

    def enabled_steps(self) -> list[Step]:
        return [s for s in self.steps if s.enabled]

    def open_gates_before(self, phase: str, state: State) -> list[Step]:
        """Enabled steps with a gate, earlier than ``phase``, that nobody has approved yet."""
        later = PHASES.index(phase)
        return [
            s
            for s in self.enabled_steps()
            if s.gate and PHASES.index(s.id) < later and not state.is_approved(s.id)
        ]

    def next_step(self, state: State) -> Step | None:
        """First enabled step that is not done. ``init`` is done once the project exists."""
        for step in self.enabled_steps():
            if step.id != "init" and not state.is_approved(step.id):
                return step
        return None


def _flag(raw: dict[str, Any], key: str, where: str, problems: list[str]) -> bool:
    value = raw.get(key, True)
    if not isinstance(value, bool):
        problems.append(f"{where}.{key} must be true or false")
        return True
    return value


def parse_workflow(text: str) -> Workflow:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkflowError(f"workflow.yml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkflowError("workflow.yml must contain a mapping")
    if str(data.get("schema_version")) != SCHEMA_VERSION:
        raise WorkflowError(f"Unsupported workflow.yml schema_version; expected {SCHEMA_VERSION!r}")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowError("workflow.yml needs a non-empty `steps` list")

    problems: list[str] = []
    steps: list[Step] = []
    for n, raw in enumerate(raw_steps, 1):
        where = f"steps[{n}]"
        if not isinstance(raw, dict):
            problems.append(f"{where} must be a mapping")
            continue
        unknown = set(raw) - _STEP_KEYS
        if unknown:
            problems.append(f"{where} has unknown key(s): {', '.join(sorted(map(str, unknown)))}")
        step_id = raw.get("id")
        if step_id not in PHASES:
            problems.append(f"{where}.id must be one of {', '.join(PHASES)}, got {step_id!r}")
            continue
        produces = raw.get("produces") or []
        if not isinstance(produces, list) or not all(isinstance(p, str) for p in produces):
            problems.append(f"{where}.produces must be a list of paths")
            produces = []
        title, skill = raw.get("title"), raw.get("skill")
        for key, value in (("title", title), ("skill", skill)):
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}.{key} must be a non-empty string")
        steps.append(
            Step(
                id=step_id,
                title=title if isinstance(title, str) else "",
                skill=skill if isinstance(skill, str) else "",
                gate=_flag(raw, "gate", where, problems),
                enabled=_flag(raw, "enabled", where, problems),
                produces=tuple(produces),
            )
        )

    ids = [s.id for s in steps]
    if len(set(ids)) != len(ids):
        problems.append("steps must not repeat an id")
    if [i for i in PHASES if i in ids] != ids:
        problems.append(f"steps must follow this order: {', '.join(PHASES)}")
    if problems:
        raise WorkflowError("Invalid workflow.yml: " + "; ".join(problems))
    return Workflow(steps)


def default_workflow() -> Workflow:
    text = (files("project_kit") / "assets" / "project" / "workflow.yml").read_text("utf-8")
    return parse_workflow(text)


def load_workflow(root: Path) -> Workflow:
    """The project's workflow, or the shipped one for projects created before it existed."""
    path = workflow_path(root)
    if not path.exists():
        return default_workflow()
    return parse_workflow(path.read_text(encoding="utf-8"))


def step_marks(workflow: Workflow, state: State) -> list[tuple[Step, str, str]]:
    """Each step with its mark (``x`` done, ``>`` next, ``-`` skipped, blank pending) and note."""
    next_step = workflow.next_step(state)
    marks = []
    for step in workflow.steps:
        if not step.enabled:
            mark, note = "-", "skipped (disabled in workflow.yml)"
        elif step.id == "init" or state.is_approved(step.id):
            mark, note = "x", "done"
        elif step is next_step:
            mark, note = ">", "next"
        else:
            mark, note = " ", "pending"
        marks.append((step, mark, note))
    return marks


def render_status(workflow: Workflow, state: State, project_name: str) -> str:
    next_step = workflow.next_step(state)
    lines = [f"Project: {project_name}", ""]
    for step, mark, note in step_marks(workflow, state):
        lines.append(f"  [{mark}] {step.id:<10} /{step.skill:<12} {note}")
    lines.append("")
    if next_step is None:
        lines.append("Every enabled phase is done.")
    else:
        lines.append(f"Next: /{next_step.skill}: {next_step.title}")
    return "\n".join(lines)
