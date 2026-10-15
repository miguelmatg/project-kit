"""``project-kit provision``, part 1: milestones, labels and permanent branches on GitHub.

The flow is plan -> show -> confirm -> apply. Planning only reads from GitHub, and only
*missing* things are created: anything that already exists is left exactly as it is, so
running it again changes nothing and never overwrites manual edits.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from project_kit.backlog import Backlog, load_backlog
from project_kit.config import Config, ConfigError, load_config
from project_kit.gh import GhError
from project_kit.labels import PRIORITY_LABELS, TYPE_LABELS
from project_kit.providers.github import GitHubProvider, Snapshot
from project_kit.provision_issues import (
    IssuePlan,
    apply_issues,
    plan_issues,
    project_title,
    read_world,
    record_existing,
)
from project_kit.state import State, load_state, save_state

_KIND_ORDER = {"milestone": 0, "label": 1, "branch": 2}


@dataclass(frozen=True)
class Action:
    """One thing to create. ``color``/``sha`` are only meaningful for labels/branches."""

    kind: str  # "milestone" | "label" | "branch"
    name: str
    description: str = ""
    color: str = ""
    sha: str = ""
    phase_id: str = ""  # milestones: the backlog phase this one belongs to

    def describe(self) -> str:
        if self.kind == "label":
            return f"+ label      {self.name}  (#{self.color})"
        if self.kind == "branch":
            return f"+ branch     {self.name}  (from {self.sha[:7]})"
        return f"+ milestone  {self.name}"


@dataclass
class Plan:
    actions: list[Action] = field(default_factory=list)
    existing: dict[str, int] = field(default_factory=dict)  # kind -> how many already exist
    milestone_ids: dict[str, int] = field(default_factory=dict)  # phase id -> number, existing
    problems: list[str] = field(default_factory=list)  # blocking: nothing can be applied


def _desired_labels(backlog: Backlog) -> list[tuple[str, str, str]]:
    wanted: dict[str, tuple[str, str, str]] = {}
    for issue in backlog.issues:
        for label in (TYPE_LABELS[issue.type], PRIORITY_LABELS[issue.priority]):
            wanted.setdefault(label[0].lower(), label)
    for label in backlog.labels:
        wanted.setdefault(label.name.lower(), (label.name, label.color, label.description))
    return list(wanted.values())


def build_plan(backlog: Backlog, config: Config, snap: Snapshot) -> Plan:
    plan = Plan()
    existing = {"milestone": 0, "label": 0, "branch": 0}

    for phase in backlog.phases:
        number = snap.milestones.get(phase.title)
        if number is None:
            plan.actions.append(
                Action("milestone", phase.title, phase.description, phase_id=phase.id)
            )
        else:
            existing["milestone"] += 1
            plan.milestone_ids[phase.id] = number

    for name, color, description in _desired_labels(backlog):
        if name.lower() in snap.labels:
            existing["label"] += 1
        else:
            plan.actions.append(Action("label", name, description, color))

    main = config.branches["main"]
    if snap.repo.default_branch and snap.repo.default_branch != main:
        plan.problems.append(
            f"config.yml says the main branch is {main!r} but the repository's default "
            f"branch is {snap.repo.default_branch!r}. Fix branches.main in config.yml."
        )
    main_sha = snap.branches.get(main)
    if main_sha is None:
        plan.problems.append(
            f"Branch {main!r} does not exist in {snap.repo.full_name}. Push an initial "
            "commit first: new branches are created from it."
        )
    for key in ("release", "develop"):
        name = config.branches[key]
        if name in snap.branches:
            existing["branch"] += 1
        elif main_sha:
            plan.actions.append(Action("branch", name, sha=main_sha))
    if main_sha:
        existing["branch"] += 1

    plan.existing = existing
    plan.actions.sort(key=lambda a: _KIND_ORDER[a.kind])
    return plan


def protection_note(available: bool | None) -> str:
    if available is False:
        return (
            "Branch protection: NOT available (private repository on a plan without it). "
            "Not attempted. Enforce the branch rules by convention and write that down in "
            "your workflow rules; protect the branches once the repository is public or "
            "the plan allows it."
        )
    if available:
        return (
            "Branch protection: available, but project-kit does not configure it yet. "
            "Set it up by hand."
        )
    return "Branch protection: could not be determined. Not attempted."


def render_plan(
    plan: Plan, repo: str, protection: bool | None, issues: IssuePlan | None = None
) -> str:
    issues = issues or IssuePlan()
    lines = [f"Repository: {repo}", ""]
    if plan.actions:
        lines += ["To create:"] + [f"  {a.describe()}" for a in plan.actions]
    else:
        lines.append("Nothing to create.")
    have = ", ".join(f"{n} {kind}(s)" for kind, n in plan.existing.items() if n)
    if have:
        lines += ["", f"Already present, left untouched: {have}."]
    if issues.lines:
        lines += ["", "Project and issues:"] + [f"  {line}" for line in issues.lines]
    for note in issues.notes:
        lines += ["", f"Note: {note}"]
    lines += ["", protection_note(protection)]
    for problem in plan.problems:
        lines += ["", f"BLOCKING: {problem}"]
    return "\n".join(lines)


def _record_milestones(state: State, ids: dict[str, int]) -> bool:
    changed = False
    for phase_id, number in ids.items():
        if state.get_id("milestones", phase_id) != str(number):
            state.set_id("milestones", phase_id, str(number))
            changed = True
    return changed


def apply_plan(root: Path, provider: GitHubProvider, plan: Plan, state: State) -> None:
    """Execute the plan. Progress is saved as it goes, so a failure can be resumed."""
    for action in plan.actions:
        if action.kind == "milestone":
            number = provider.create_milestone(action.name, action.description)
            state.set_id("milestones", action.phase_id, str(number))
            save_state(root, state)
        elif action.kind == "label":
            provider.create_label(action.name, action.color, action.description)
        else:
            provider.create_branch(action.name, action.sha)


def _mark_provisioned(root: Path, state: State) -> None:
    """Save the state and record this phase as done (it has no approval prompt of its own)."""
    if not state.is_approved("provision"):
        state.approve("provision")
    save_state(root, state)


def run_provision(
    root: Path,
    provider: GitHubProvider,
    *,
    dry_run: bool,
    assume_yes: bool,
    confirm: Callable[[str], bool],
    out: Callable[[str], None] = print,
) -> int:
    """Returns the process exit code."""
    config = load_config(root)
    if config.provider != "github":
        raise ConfigError(f"Provider {config.provider!r} is not supported yet; use 'github'.")
    backlog = load_backlog(root)
    state = load_state(root)

    if not dry_run and not state.is_approved("plan"):
        out("The plan is not approved yet. Run the pk-plan skill, or `project-kit approve plan`.")
        return 1

    snap = provider.snapshot()
    protection = provider.branch_protection_available()
    plan = build_plan(backlog, config, snap)
    owner = snap.repo.owner
    world = read_world(provider, owner, project_title(config))
    issue_plan = plan_issues(backlog, config, world, state)
    out(render_plan(plan, snap.repo.full_name, protection, issue_plan))

    if plan.problems:
        return 1
    if dry_run:
        out("\nDry run: nothing was changed.")
        return 0

    total = len(plan.actions) + len(issue_plan.lines)
    if not total:
        # Nothing to change on GitHub, but a lost or stale state can still be rebuilt.
        _record_milestones(state, plan.milestone_ids)
        record_existing(backlog, world, state)
        _mark_provisioned(root, state)
        out("\nNothing to do.")
        return 0

    if not assume_yes and not confirm(f"\nApply these {total} change(s) in {snap.repo.full_name}?"):
        out("Aborted. Nothing was changed.")
        return 1

    _record_milestones(state, plan.milestone_ids)
    try:
        apply_plan(root, provider, plan, state)
        notes = apply_issues(
            provider, owner, backlog, config, state, lambda: save_state(root, state)
        )
    except GhError as exc:
        save_state(root, state)
        out(f"\nStopped: {exc}\nProgress was saved; run the command again to resume.")
        return 1
    _mark_provisioned(root, state)
    for note in notes:
        out(f"\nNote: {note}")
    out(f"\nDone: {total} change(s) applied.")
    return 0
