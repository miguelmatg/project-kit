import json
import subprocess

import pytest

from project_kit import installer
from project_kit.approval import approve_phase
from project_kit.backlog import backlog_path, parse_backlog
from project_kit.config import Config
from project_kit.gh import Gh, GhError
from project_kit.providers.github import GitHubProvider, RepoInfo, Snapshot
from project_kit.provision import build_plan, protection_note, run_provision
from project_kit.state import load_state

BACKLOG = {
    "version": 1,
    "phases": [
        {"id": "mvp", "title": "v0.1", "description": "First"},
        {"id": "later", "title": "v0.2"},
    ],
    "labels": [{"name": "area:x", "color": "0E8A16", "description": "X"}],
    "issues": [
        {"id": "e", "type": "epic", "phase": "mvp", "title": "E", "priority": "P1", "size": "L"},
        {
            "id": "b",
            "type": "bug",
            "phase": "later",
            "title": "B",
            "priority": "P0",
            "size": "S",
            "parent": "e",
            "labels": ["area:x"],
            "acceptance": ["fixed"],
        },
    ],
}


def repo_info(default="main", private=True):
    return RepoInfo("o/r", private, default, True)


def snapshot(**kw):
    base = dict(
        repo=repo_info(),
        labels=set(),
        milestones={},
        branches={"main": "a" * 40},
    )
    return Snapshot(**{**base, **kw})


class FakeProvider:
    """In-memory stand-in for GitHubProvider that also behaves like GitHub afterwards."""

    def __init__(self, snap, protection=False, fail_on=None):
        self.snap = snap
        self.protection = protection
        self.fail_on = fail_on
        self.calls = []

    def snapshot(self):
        return self.snap

    def branch_protection_available(self):
        return self.protection

    def _maybe_fail(self, what):
        if self.fail_on == what:
            self.fail_on = None
            raise GhError(f"boom on {what}")

    def create_milestone(self, title, description):
        self._maybe_fail(f"milestone:{title}")
        number = len(self.snap.milestones) + 1
        self.snap.milestones[title] = number
        self.calls.append(("milestone", title))
        return number

    def create_label(self, name, color, description):
        self._maybe_fail(f"label:{name}")
        self.snap.labels.add(name.lower())
        self.calls.append(("label", name, color))

    def create_branch(self, name, sha):
        self._maybe_fail(f"branch:{name}")
        self.snap.branches[name] = sha
        self.calls.append(("branch", name, sha))


@pytest.fixture
def project(tmp_path):
    installer.init_project(tmp_path, Config(project_name="demo"))
    backlog_path(tmp_path).write_text(json.dumps(BACKLOG), encoding="utf-8")
    approve_phase(tmp_path, "plan")
    return tmp_path


def run(project, provider, *, dry_run=False, yes=True, answer=True):
    out = []
    asked = []

    def confirm(question):
        asked.append(question)
        return answer

    code = run_provision(
        project, provider, dry_run=dry_run, assume_yes=yes, confirm=confirm, out=out.append
    )
    return code, "\n".join(out), asked


# --- planning ------------------------------------------------------------------------------


def plan_for(snap):
    return build_plan(parse_backlog(json.dumps(BACKLOG)), Config(project_name="d"), snap)


def test_plan_derives_labels_from_types_priorities_and_declared_labels():
    plan = plan_for(snapshot())
    labels = {a.name: a for a in plan.actions if a.kind == "label"}
    assert set(labels) == {"type:epic", "bug", "P1", "P0", "area:x"}
    assert labels["area:x"].color == "0E8A16"
    assert [a.name for a in plan.actions if a.kind == "milestone"] == ["v0.1", "v0.2"]
    assert [(a.name, a.sha[:1]) for a in plan.actions if a.kind == "branch"] == [
        ("release", "a"),
        ("develop", "a"),
    ]


def test_plan_orders_milestones_then_labels_then_branches():
    kinds = [a.kind for a in plan_for(snapshot()).actions]
    assert kinds == sorted(kinds, key=["milestone", "label", "branch"].index)


def test_existing_items_are_skipped_case_insensitively():
    snap = snapshot(
        labels={"type:epic", "bug", "p1", "p0", "area:x"},
        milestones={"v0.1": 7, "v0.2": 8},
        branches={"main": "a" * 40, "release": "b" * 40, "develop": "c" * 40},
    )
    plan = plan_for(snap)
    assert plan.actions == []
    assert plan.milestone_ids == {"mvp": 7, "later": 8}
    assert plan.existing == {"milestone": 2, "label": 5, "branch": 3}


def test_main_branch_must_match_default_branch():
    plan = plan_for(snapshot(repo=repo_info(default="master")))
    assert any("default branch is 'master'" in p for p in plan.problems)


def test_empty_repository_is_a_blocking_problem():
    plan = plan_for(snapshot(branches={}))
    assert any("initial commit" in p for p in plan.problems)
    assert not [a for a in plan.actions if a.kind == "branch"]


# --- running -------------------------------------------------------------------------------


def test_apply_creates_everything_and_records_milestone_ids(project):
    provider = FakeProvider(snapshot())
    code, out, _ = run(project, provider)
    assert code == 0 and "Done: 9 item(s) created." in out
    assert [c[0] for c in provider.calls] == ["milestone"] * 2 + ["label"] * 5 + ["branch"] * 2
    state = load_state(project)
    assert state.get_id("milestones", "mvp") == "1"
    assert state.get_id("milestones", "later") == "2"


def test_second_run_is_idempotent(project):
    provider = FakeProvider(snapshot())
    run(project, provider)
    provider.calls.clear()
    code, out, asked = run(project, provider, yes=False)
    assert code == 0 and "Nothing to do." in out
    assert provider.calls == [] and asked == []  # nothing to change, so nothing to confirm


def test_dry_run_changes_nothing_and_does_not_need_approval(project):
    state = load_state(project)
    state.approvals.clear()
    from project_kit.state import save_state

    save_state(project, state)
    provider = FakeProvider(snapshot())
    code, out, asked = run(project, provider, dry_run=True, yes=False)
    assert code == 0 and "Dry run: nothing was changed." in out
    assert "+ milestone  v0.1" in out and "+ branch     develop" in out
    assert provider.calls == [] and asked == []
    assert load_state(project).provider_ids == {}


def test_confirmation_is_required_and_a_no_aborts(project):
    provider = FakeProvider(snapshot())
    code, out, asked = run(project, provider, yes=False, answer=False)
    assert code == 1 and "Aborted" in out
    assert provider.calls == [] and len(asked) == 1 and "9 item(s)" in asked[0]


def test_yes_skips_the_question(project):
    code, _, asked = run(project, FakeProvider(snapshot()), yes=True)
    assert code == 0 and asked == []


def test_applying_requires_an_approved_plan(project):
    state = load_state(project)
    state.approvals.clear()
    from project_kit.state import save_state

    save_state(project, state)
    provider = FakeProvider(snapshot())
    code, out, _ = run(project, provider)
    assert code == 1 and "not approved" in out and provider.calls == []


def test_blocking_problem_stops_before_applying(project):
    provider = FakeProvider(snapshot(branches={}))
    code, out, _ = run(project, provider)
    assert code == 1 and "BLOCKING" in out and provider.calls == []
    code, _, _ = run(project, provider, dry_run=True)
    assert code == 1


def test_failure_saves_progress_and_a_rerun_resumes(project):
    provider = FakeProvider(snapshot(), fail_on="label:P1")
    code, out, _ = run(project, provider)
    assert code == 1 and "Stopped" in out and "run the command again" in out
    done = list(provider.calls)
    assert ("milestone", "v0.1") in done and not any(c[0] == "branch" for c in done)
    assert load_state(project).get_id("milestones", "mvp") == "1"

    provider.calls.clear()
    code, out, _ = run(project, provider)
    assert code == 0
    created = {c[1] for c in provider.calls}
    assert not created & {"v0.1", "v0.2", "type:epic"}  # earlier work is not repeated
    assert {"P1", "release", "develop"} <= created


def test_existing_milestones_are_recorded_in_state(project):
    snap = snapshot(milestones={"v0.1": 11, "v0.2": 12})
    run(project, FakeProvider(snap))
    assert load_state(project).get_id("milestones", "later") == "12"


def test_gitlab_provider_is_rejected(project):
    (project / ".project-kit/config.yml").write_text(
        "project_name: demo\nprovider: gitlab\n", encoding="utf-8"
    )
    from project_kit.config import ConfigError

    with pytest.raises(ConfigError, match="not supported yet"):
        run(project, FakeProvider(snapshot()))


# --- branch protection ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("available", "text"),
    [
        (False, "NOT available"),
        (True, "does not configure it yet"),
        (None, "could not be determined"),
    ],
)
def test_protection_note(available, text):
    assert text in protection_note(available)


def test_protection_is_reported_but_never_attempted(project):
    provider = FakeProvider(snapshot(), protection=False)
    _, out, _ = run(project, provider, dry_run=True)
    assert "NOT available" in out and "Not attempted" in out


# --- the GitHub adapter itself -------------------------------------------------------------


class Script:
    """Fake subprocess runner returning scripted stdout/stderr per call."""

    def __init__(self, *results):
        self.results = list(results)
        self.cmds = []

    def __call__(self, cmd, **kwargs):
        self.cmds.append(cmd[1:])
        code, out, err = self.results.pop(0)
        return subprocess.CompletedProcess(cmd, code, stdout=out, stderr=err)


def provider_with(*results, repo="o/r"):
    script = Script(*results)
    return GitHubProvider(Gh(retries=0, runner=script, sleep=lambda s: None), repo), script


def ok(data):
    return (0, json.dumps(data), "")


def test_snapshot_collects_labels_milestones_and_branches():
    info = {
        "nameWithOwner": "o/r",
        "isPrivate": True,
        "defaultBranchRef": {"name": "main"},
        "viewerPermission": "ADMIN",
    }
    provider, script = provider_with(
        ok(info),
        ok([{"name": "Bug"}, {"name": "type:epic"}]),
        ok([{"title": "v0.1", "number": 3}]),
        ok([{"name": "main", "commit": {"sha": "abc"}}]),
    )
    snap = provider.snapshot()
    assert snap.labels == {"bug", "type:epic"}
    assert snap.milestones == {"v0.1": 3}
    assert snap.branches == {"main": "abc"}
    assert snap.repo.private and snap.repo.default_branch == "main" and snap.repo.can_admin
    assert script.cmds[2][1].startswith("repos/o/r/milestones?state=all&per_page=100&page=1")


def test_paging_follows_full_pages():
    full = [{"title": f"m{i}", "number": i} for i in range(100)]
    provider, script = provider_with(ok(full), ok([{"title": "last", "number": 100}]))
    items = provider._paged("repos/o/r/milestones?state=all")
    assert len(items) == 101
    assert script.cmds[1][1].endswith("page=2")


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ((0, "[]", ""), True),
        (
            (1, "", "Upgrade to GitHub Pro or make this repository public to enable this feature."),
            False,
        ),
        ((1, "", "HTTP 500 something else entirely"), None),
    ],
)
def test_protection_probe(result, expected):
    provider, _ = provider_with(result)
    assert provider.branch_protection_available() is expected


def test_write_commands_use_the_expected_arguments():
    provider, script = provider_with((0, "", ""), ok({"number": 9}), (0, "", ""), repo="o/r")
    provider.create_label("P1", "D93F0B", "High")
    assert provider.create_milestone("v0.1", "First") == 9
    provider.create_branch("develop", "abc123")
    label, milestone, branch = script.cmds
    assert label == [
        "label",
        "create",
        "P1",
        "--repo",
        "o/r",
        "--color",
        "D93F0B",
        "--description",
        "High",
    ]
    assert milestone[:4] == ["api", "-X", "POST", "repos/o/r/milestones"]
    assert "title=v0.1" in milestone and "description=First" in milestone
    assert "ref=refs/heads/develop" in branch and "sha=abc123" in branch
