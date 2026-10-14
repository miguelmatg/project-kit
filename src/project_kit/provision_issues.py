"""``project-kit provision``, part 2: the GitHub Project and the backlog issues.

Both planning and applying start from a fresh read of GitHub (``read_world``) and never
trust a stored plan, so a run that died half way is simply continued by running it again.

Rules that keep it safe to repeat:

* An issue is identified by a hidden marker in its body (``project-kit:id=<local id>``) in
  addition to ``state.json``, so losing the state does not duplicate issues.
* Existing issues are never rewritten, except the *child issues* block of an epic, which
  project-kit owns (ticked boxes are preserved).
* Project fields are only filled when empty. Status in particular is set once, to Backlog,
  so cards the user has moved are never moved back.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from project_kit.backlog import Backlog, Issue
from project_kit.config import Config
from project_kit.labels import PRIORITY_LABELS, TYPE_LABELS
from project_kit.providers.github import (
    GitHubProvider,
    ProjectItem,
    ProjectRef,
    RemoteIssue,
    SelectField,
    SelectOption,
)
from project_kit.state import State

STATUS_OPTIONS = [
    SelectOption("Backlog", "GRAY", "Not prioritised yet"),
    SelectOption("Ready", "BLUE", "Ready to start"),
    SelectOption("In progress", "YELLOW", "Being worked on"),
    SelectOption("In review", "ORANGE", "Pull request open"),
    SelectOption("Done", "GREEN", "Merged"),
]
# What GitHub puts in a brand-new Project. Only in this exact shape (and with no items yet)
# is the Status field safe to replace: replacing it resets the status of existing items.
_DEFAULT_STATUS = {"Todo", "In Progress", "Done"}

KIND_OF_TYPE = {
    "epic": "Epic",
    "feature": "Feature",
    "adr": "ADR",
    "chore": "Chore",
    "bug": "Bug",
    "docs": "Docs",
}
_STATIC_FIELDS = {
    "Kind": list(KIND_OF_TYPE.values()),
    "Priority": ["P0", "P1", "P2", "P3"],
    "Size": ["XS", "S", "M", "L", "XL"],
}

_CHILDREN_RE = re.compile(
    r"<!-- project-kit:children:start -->.*?<!-- project-kit:children:end -->", re.DOTALL
)
_MARKER_RE = re.compile(r"<!--\s*project-kit:id=[a-z0-9-]+\s*-->")
_CHILD_LINE = re.compile(r"^- \[([ xX])\] #(\d+)", re.MULTILINE)


def project_title(config: Config) -> str:
    return f"{config.project_name} Roadmap"


# --- issue bodies ------------------------------------------------------------------------


def build_body(issue: Issue, parent_number: int | None) -> str:
    parts = []
    if parent_number:
        parts.append(f"Part of #{parent_number}.")
    if issue.body.strip():
        parts.append(issue.body.strip())
    if issue.acceptance:
        checklist = "\n".join(f"- [ ] {item}" for item in issue.acceptance)
        parts.append(f"## Acceptance criteria\n{checklist}")
    parts.append(f"<!-- project-kit:id={issue.id} -->")
    return "\n\n".join(parts) + "\n"


def with_children_block(body: str, numbers: list[int]) -> str:
    """Return ``body`` with the epic's child list set to ``numbers``.

    Boxes the user already ticked stay ticked. The block replaces the previous one, or goes
    just before the identifying marker (or at the end) the first time.
    """
    ticked = {int(n) for mark, n in _CHILD_LINE.findall(body) if mark in "xX"}
    lines = "\n".join(f"- [{'x' if n in ticked else ' '}] #{n}" for n in numbers)
    block = (
        "<!-- project-kit:children:start -->\n"
        f"## Child issues\n{lines}\n"
        "<!-- project-kit:children:end -->"
    )
    if _CHILDREN_RE.search(body):
        return _CHILDREN_RE.sub(lambda _: block, body, count=1)
    marker = _MARKER_RE.search(body)
    if marker:
        return body[: marker.start()] + block + "\n\n" + body[marker.start() :]
    return body.rstrip("\n") + "\n\n" + block + "\n"


def issue_labels(issue: Issue) -> list[str]:
    return [TYPE_LABELS[issue.type][0], PRIORITY_LABELS[issue.priority][0], *issue.labels]


# --- reading the current state -----------------------------------------------------------


@dataclass
class World:
    project: ProjectRef | None
    fields: dict[str, SelectField] = field(default_factory=dict)
    items: list[ProjectItem] = field(default_factory=list)
    issues: list[RemoteIssue] = field(default_factory=list)

    def remote_by_local_id(self, state: State) -> dict[str, RemoteIssue]:
        """Existing issues keyed by backlog id: by marker, or by the number in the state."""
        by_number = {i.number: i for i in self.issues}
        found = {i.local_id: i for i in self.issues if i.local_id}
        for local_id, number in state.provider_ids.get("issues", {}).items():
            if local_id not in found and int(number) in by_number:
                found[local_id] = by_number[int(number)]
        return found


def read_world(provider: GitHubProvider, owner: str, title: str) -> World:
    project = provider.find_project(owner, title)
    world = World(project, issues=provider.list_issues())
    if project:
        world.fields = provider.project_fields(owner, project)
        world.items = provider.project_items(owner, project)
    return world


def _wanted_fields(backlog: Backlog) -> dict[str, list[str]]:
    return {"Phase": [p.title for p in backlog.phases], **_STATIC_FIELDS}


def _item_values(backlog: Backlog, issue: Issue) -> dict[str, tuple[str, str]]:
    """The values project-kit wants on an item: lower-cased field -> (field name, option)."""
    phase = next(p.title for p in backlog.phases if p.id == issue.phase)
    return {
        "status": ("Status", "Backlog"),
        "phase": ("Phase", phase),
        "kind": ("Kind", KIND_OF_TYPE[issue.type]),
        "priority": ("Priority", issue.priority),
        "size": ("Size", issue.size),
    }


def _epic_numbers(backlog: Backlog, epic: Issue, remote: dict[str, RemoteIssue]) -> list[int]:
    return [remote[c.id].number for c in backlog.children_of(epic.id) if c.id in remote]


def _status_is_replaceable(world: World) -> bool:
    status = world.fields.get("Status")
    return bool(status) and set(status.options) == _DEFAULT_STATUS and not world.items


# --- planning ----------------------------------------------------------------------------


@dataclass
class IssuePlan:
    lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def plan_issues(backlog: Backlog, config: Config, world: World, state: State) -> IssuePlan:
    plan = IssuePlan()
    remote = world.remote_by_local_id(state)

    if world.project is None:
        plan.lines.append(f"+ project    {project_title(config)}  (linked to the repository)")
    else:
        for name, options in _wanted_fields(backlog).items():
            current = world.fields.get(name)
            if current is None:
                plan.lines.append(f"+ field      {name}  ({len(options)} option(s))")
            elif missing := [o for o in options if o not in current.options]:
                plan.lines.append(f"~ field      {name}: add {', '.join(missing)}")
        if _status_is_replaceable(world):
            plan.lines.append("~ field      Status: Backlog, Ready, In progress, In review, Done")
        elif "Status" in world.fields:
            missing = [
                o.name for o in STATUS_OPTIONS if o.name not in world.fields["Status"].options
            ]
            if missing:
                plan.notes.append(
                    f"Status field has no option(s) {', '.join(missing)}; it is left as it is, "
                    "so new items get no Status. Add them in the Project settings."
                )
    if world.project is None:
        plan.lines.append("+ fields     Phase, Kind, Priority, Size, and the Status options")

    to_create = [i for i in backlog.issues if i.id not in remote]
    for issue in to_create:
        plan.lines.append(f"+ issue      {issue.id}: {issue.title}")

    for epic in (i for i in backlog.issues if i.type == "epic"):
        children = backlog.children_of(epic.id)
        if not children:
            continue
        if epic.id not in remote or any(c.id not in remote for c in children):
            plan.lines.append(f"~ epic       {epic.id}: list {len(children)} child issue(s)")
        elif (
            with_children_block(remote[epic.id].body, _epic_numbers(backlog, epic, remote))
            != remote[epic.id].body
        ):
            plan.lines.append(f"~ epic       {epic.id}: update the child issue list")

    by_number = {i.number: i for i in world.items if i.number is not None}
    new_items = fill = 0
    for issue in backlog.issues:
        existing = remote.get(issue.id)
        item = by_number.get(existing.number) if existing else None
        if item is None:
            new_items += 1
            continue
        wanted = _item_values(backlog, issue)
        if any(
            key not in item.values
            and wanted[key][1] in world.fields.get(wanted[key][0], SelectField("", "")).options
            for key in wanted
        ):
            fill += 1
    if new_items:
        plan.lines.append(
            f"+ items      {new_items} issue(s) added to the Project with their fields"
        )
    if fill:
        plan.lines.append(f"~ items      {fill} existing item(s) get their empty fields filled")
    return plan


# --- applying ----------------------------------------------------------------------------


def _ensure_fields(
    provider: GitHubProvider,
    owner: str,
    project: ProjectRef,
    backlog: Backlog,
    items: list[ProjectItem],
) -> dict[str, SelectField]:
    fields = provider.project_fields(owner, project)
    for name, options in _wanted_fields(backlog).items():
        current = fields.get(name)
        if current is None:
            provider.create_select_field(project, name, [SelectOption(o) for o in options])
        elif missing := [o for o in options if o not in current.options]:
            keep = provider.field_options(current.id)  # existing options keep their ids
            provider.set_select_options(current.id, keep + [SelectOption(o) for o in missing])

    status = fields.get("Status")
    if status and set(status.options) == _DEFAULT_STATUS and not items:
        provider.set_select_options(status.id, STATUS_OPTIONS)
    return provider.project_fields(owner, project)


def apply_issues(
    provider: GitHubProvider,
    owner: str,
    backlog: Backlog,
    config: Config,
    state: State,
    save: Callable[[], None],  # called after every state change, so progress survives a crash
) -> list[str]:
    """Create/sync the Project and issues. Returns non-blocking notes for the user."""
    notes: list[str] = []
    world = read_world(provider, owner, project_title(config))

    project = world.project
    if project is None:
        project = provider.create_project(owner, project_title(config))
        world.items = []
    state.set_id("project", "number", str(project.number))
    state.set_id("project", "id", project.id)
    save()
    provider.link_project(owner, project)
    fields = _ensure_fields(provider, owner, project, backlog, world.items)

    # Issues: epics first, so their children can say "Part of #N".
    remote = world.remote_by_local_id(state)
    ordered = sorted(backlog.issues, key=lambda i: i.type != "epic")
    for issue in ordered:
        if issue.id in remote:
            state.set_id("issues", issue.id, str(remote[issue.id].number))
            continue
        parent = remote.get(issue.parent) if issue.parent else None
        phase = next(p for p in backlog.phases if p.id == issue.phase)
        created = provider.create_issue(
            issue.title,
            build_body(issue, parent.number if parent else None),
            phase.title,
            issue_labels(issue),
        )
        remote[issue.id] = created
        state.set_id("issues", issue.id, str(created.number))
        save()
    save()

    for epic in (i for i in backlog.issues if i.type == "epic"):
        numbers = _epic_numbers(backlog, epic, remote)
        if not numbers:
            continue
        current = remote[epic.id]
        body = with_children_block(current.body, numbers)
        if body != current.body:
            provider.update_issue_body(current.number, body)
            remote[epic.id] = RemoteIssue(current.number, current.title, body, current.url)

    by_number = {i.number: i for i in world.items if i.number is not None}
    skipped: set[str] = set()
    for issue in backlog.issues:
        issue_remote = remote[issue.id]
        item = by_number.get(issue_remote.number)
        item_id = item.id if item else provider.add_item(owner, project, issue_remote.url)
        have = item.values if item else {}
        values = {}
        for key, (field_name, option) in _item_values(backlog, issue).items():
            if key in have:
                continue  # never overwrite: the user may have changed it on purpose
            select = fields.get(field_name)
            if select is None or option not in select.options:
                skipped.add(f"{field_name}={option}")
                continue
            values[select.id] = select.options[option]
        provider.set_item_values(project, item_id, values)
        state.set_id("items", issue.id, item_id)
    save()

    if skipped:
        notes.append(
            "Some field values could not be set because the option does not exist in the "
            f"Project ({', '.join(sorted(skipped))}). Add the options in the Project settings."
        )
    return notes


def record_existing(backlog: Backlog, world: World, state: State) -> bool:
    """Write what already exists on GitHub into the state, without touching GitHub.

    Lets a lost or stale ``state.json`` be rebuilt by a run that has nothing to change.
    Returns whether the state changed.
    """
    before = {k: dict(v) for k, v in state.provider_ids.items()}
    if world.project:
        state.set_id("project", "number", str(world.project.number))
        state.set_id("project", "id", world.project.id)
    remote = world.remote_by_local_id(state)
    by_number = {i.number: i for i in world.items if i.number is not None}
    for issue in backlog.issues:
        if issue.id not in remote:
            continue
        state.set_id("issues", issue.id, str(remote[issue.id].number))
        if item := by_number.get(remote[issue.id].number):
            state.set_id("items", issue.id, item.id)
    return state.provider_ids != before
