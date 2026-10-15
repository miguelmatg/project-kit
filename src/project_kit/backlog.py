""".project-kit/backlog.json: the project backlog, source of truth for provisioning.

Shape (see docs/backlog-schema.md for the full description)::

    {
      "version": 1,
      "phases":  [{"id", "title", "description"?}],          # -> milestones / Phase field
      "labels":  [{"name", "color"?, "description"?}],       # extra labels, optional
      "issues":  [{"id", "type", "phase", "title", "priority", "size",
                   "parent"?, "body"?, "acceptance"?, "labels"?}]
    }

Validation collects every problem it finds, so the user can fix them in one pass.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from project_kit.config import PROJECT_DIR
from project_kit.fsutil import atomic_write_text

BACKLOG_VERSION = 1
ISSUE_TYPES = ("epic", "feature", "adr", "chore", "bug", "docs")
PRIORITIES = ("P0", "P1", "P2", "P3")
SIZES = ("XS", "S", "M", "L", "XL")
# Work that gets implemented needs a definition of done; epics and decisions do not.
NEEDS_ACCEPTANCE = frozenset({"feature", "bug", "chore"})

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
_DEFAULT_COLOR = "ededed"


class BacklogError(ValueError):
    """The backlog is missing, unreadable or invalid. ``problems`` lists every issue found."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("Invalid backlog:\n" + "\n".join(f"  - {p}" for p in problems))
        self.problems = problems


def backlog_path(root: Path) -> Path:
    return root / PROJECT_DIR / "backlog.json"


@dataclass
class Phase:
    id: str
    title: str
    description: str = ""


@dataclass
class Label:
    name: str
    color: str = _DEFAULT_COLOR
    description: str = ""


@dataclass
class Issue:
    id: str
    type: str
    phase: str
    title: str
    priority: str
    size: str
    parent: str | None = None
    body: str = ""
    acceptance: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)


@dataclass
class Backlog:
    phases: list[Phase] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)

    def children_of(self, epic_id: str) -> list[Issue]:
        return [i for i in self.issues if i.parent == epic_id]

    def summary(self) -> str:
        by_type = Counter(i.type for i in self.issues)
        lines = [f"{len(self.phases)} phase(s), {len(self.issues)} issue(s)"]
        for phase in self.phases:
            items = [i for i in self.issues if i.phase == phase.id]
            counts = ", ".join(f"{by}: {n}" for by, n in Counter(i.type for i in items).items())
            lines.append(f"  {phase.title}: {len(items)} ({counts or 'empty'})")
        if by_type:
            lines.append(
                "by priority: "
                + ", ".join(
                    f"{p}: {n}" for p, n in sorted(Counter(i.priority for i in self.issues).items())
                )
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        def issue(i: Issue) -> dict[str, Any]:
            d: dict[str, Any] = {
                "id": i.id,
                "type": i.type,
                "phase": i.phase,
                "title": i.title,
                "priority": i.priority,
                "size": i.size,
            }
            if i.parent:
                d["parent"] = i.parent
            if i.body:
                d["body"] = i.body
            if i.acceptance:
                d["acceptance"] = list(i.acceptance)
            if i.labels:
                d["labels"] = list(i.labels)
            return d

        return {
            "version": BACKLOG_VERSION,
            "phases": [
                {k: v for k, v in vars(p).items() if v != ""} | {"id": p.id, "title": p.title}
                for p in self.phases
            ],
            "labels": [{k: v for k, v in vars(label).items() if v != ""} for label in self.labels],
            "issues": [issue(i) for i in self.issues],
        }


class _Collector:
    """Reads typed values out of untyped JSON, recording problems instead of raising."""

    def __init__(self) -> None:
        self.problems: list[str] = []

    def add(self, where: str, message: str) -> None:
        self.problems.append(f"{where}: {message}")

    def obj(self, value: Any, where: str, allowed: set[str]) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.add(where, "must be an object")
            return None
        for key in sorted(set(value) - allowed, key=str):
            self.add(where, f"unknown field {key!r}")
        return value

    def text(self, data: dict[str, Any], key: str, where: str, *, required: bool = True) -> str:
        if key not in data or data[key] is None:
            if required:
                self.add(where, f"missing required field {key!r}")
            return ""
        value = data[key]
        if not isinstance(value, str):
            self.add(where, f"{key!r} must be a string")
            return ""
        if required and not value.strip():
            self.add(where, f"{key!r} must not be empty")
        return value

    def choice(self, data: dict[str, Any], key: str, where: str, options: tuple[str, ...]) -> str:
        value = self.text(data, key, where)
        if value and value not in options:
            self.add(where, f"{key!r} must be one of {', '.join(options)}, got {value!r}")
        return value

    def strings(self, data: dict[str, Any], key: str, where: str) -> list[str]:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            self.add(where, f"{key!r} must be a list of non-empty strings")
            return []
        return list(value)


def _ident(c: _Collector, data: dict[str, Any], where: str) -> str:
    value = c.text(data, "id", where)
    if value and not _ID.match(value):
        c.add(where, f"'id' must be lowercase letters, digits and hyphens, got {value!r}")
    return value


def parse_backlog(text: str) -> Backlog:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BacklogError([f"backlog.json is not valid JSON: {exc}"]) from exc

    c = _Collector()
    root = c.obj(raw, "backlog", {"version", "phases", "labels", "issues"})
    if root is None:
        raise BacklogError(c.problems)
    if root.get("version") != BACKLOG_VERSION:
        c.add(
            "backlog", f"unsupported version {root.get('version')!r} (expected {BACKLOG_VERSION})"
        )

    backlog = Backlog()

    for n, item in enumerate(root.get("phases") or [], 1):
        where = f"phases[{n}]"
        if (d := c.obj(item, where, {"id", "title", "description"})) is not None:
            backlog.phases.append(
                Phase(
                    _ident(c, d, where),
                    c.text(d, "title", where),
                    c.text(d, "description", where, required=False),
                )
            )

    for n, item in enumerate(root.get("labels") or [], 1):
        where = f"labels[{n}]"
        if (d := c.obj(item, where, {"name", "color", "description"})) is not None:
            color = c.text(d, "color", where, required=False) or _DEFAULT_COLOR
            if not _COLOR.match(color):
                c.add(where, f"'color' must be 6 hex digits without '#', got {color!r}")
            backlog.labels.append(
                Label(
                    c.text(d, "name", where),
                    color,
                    c.text(d, "description", where, required=False),
                )
            )

    allowed = {"id", "type", "phase", "title", "priority", "size", "parent", "body",
               "acceptance", "labels"}  # fmt: skip
    for n, item in enumerate(root.get("issues") or [], 1):
        where = f"issues[{n}]"
        if (d := c.obj(item, where, allowed)) is None:
            continue
        ident = _ident(c, d, where)
        where = f"issue {ident!r}" if ident else where
        parent = c.text(d, "parent", where, required=False) or None
        backlog.issues.append(
            Issue(
                id=ident,
                type=c.choice(d, "type", where, ISSUE_TYPES),
                phase=c.text(d, "phase", where),
                title=c.text(d, "title", where),
                priority=c.choice(d, "priority", where, PRIORITIES),
                size=c.choice(d, "size", where, SIZES),
                parent=parent,
                body=c.text(d, "body", where, required=False),
                acceptance=c.strings(d, "acceptance", where),
                labels=c.strings(d, "labels", where),
            )
        )

    _check_references(backlog, c)
    if c.problems:
        raise BacklogError(c.problems)
    return backlog


def _duplicates(values: list[str]) -> list[str]:
    return sorted(v for v, n in Counter(values).items() if v and n > 1)


def _check_references(backlog: Backlog, c: _Collector) -> None:
    for dup in _duplicates([p.id for p in backlog.phases]):
        c.add("phases", f"duplicate id {dup!r}")
    for dup in _duplicates([p.title for p in backlog.phases]):
        c.add("phases", f"duplicate title {dup!r}")
    for dup in _duplicates([label.name for label in backlog.labels]):
        c.add("labels", f"duplicate name {dup!r}")
    for dup in _duplicates([i.id for i in backlog.issues]):
        c.add("issues", f"duplicate id {dup!r}")

    phase_ids = {p.id for p in backlog.phases}
    declared = {label.name for label in backlog.labels}
    by_id = {i.id: i for i in backlog.issues}

    for i in backlog.issues:
        where = f"issue {i.id!r}"
        if i.phase and i.phase not in phase_ids:
            c.add(where, f"unknown phase {i.phase!r}")
        if i.type in NEEDS_ACCEPTANCE and not i.acceptance:
            c.add(where, f"a {i.type} needs at least one acceptance criterion")
        for name in i.labels:
            if name not in declared:
                c.add(where, f"label {name!r} is not declared in 'labels'")
        if i.parent is None:
            continue
        if i.type == "epic":
            c.add(where, "an epic cannot have a parent")
        parent = by_id.get(i.parent)
        if parent is None:
            c.add(where, f"unknown parent {i.parent!r}")
        elif parent.type != "epic":
            c.add(where, f"parent {i.parent!r} is a {parent.type}, not an epic")


def validate_backlog(backlog: Backlog) -> None:
    """Re-validate a backlog built in code (``parse_backlog`` validates on load)."""
    parse_backlog(json.dumps(backlog.to_dict()))


def load_backlog(root: Path) -> Backlog:
    path = backlog_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BacklogError([f"No backlog found at {path}. Run the pk-plan skill first."]) from exc
    return parse_backlog(text)


def save_backlog(root: Path, backlog: Backlog) -> None:
    validate_backlog(backlog)
    text = json.dumps(backlog.to_dict(), indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(backlog_path(root), text)
