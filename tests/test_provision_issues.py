import json
import subprocess

import pytest
from fakes import FakeGitHub, approve_through

from project_kit import installer
from project_kit.backlog import backlog_path, parse_backlog
from project_kit.config import Config
from project_kit.gh import Gh
from project_kit.providers.github import GitHubProvider, ProjectRef, SelectOption
from project_kit.provision import run_provision
from project_kit.provision_issues import (
    build_body,
    issue_labels,
    with_children_block,
)
from project_kit.state import load_state, save_state


def issue(id_, type_="feature", phase="mvp", parent=None, **kw):
    data = {
        "id": id_,
        "type": type_,
        "phase": phase,
        "title": f"Title {id_}",
        "priority": "P1",
        "size": "M",
        **kw,
    }
    if parent:
        data["parent"] = parent
    if type_ in ("feature", "bug", "chore"):
        data.setdefault("acceptance", ["it works"])
    return data


def backlog_data(*extra, phases=("mvp",)):
    titles = {"mvp": "v0.1", "later": "v0.2"}
    return {
        "version": 1,
        "phases": [{"id": p, "title": titles[p]} for p in phases],
        "issues": [
            issue("e", "epic"),
            issue("a", "adr", parent="e"),
            issue("f", parent="e", body="Context here."),
            *extra,
        ],
    }


@pytest.fixture
def project(tmp_path):
    installer.init_project(tmp_path, Config(project_name="demo"))
    write_backlog(tmp_path, backlog_data())
    approve_through(tmp_path, "plan")
    return tmp_path


def write_backlog(root, data):
    backlog_path(root).write_text(json.dumps(data), encoding="utf-8")


def run(project, gh, **kw):
    out = []
    code = run_provision(
        project,
        gh,
        dry_run=kw.get("dry_run", False),
        assume_yes=True,
        confirm=lambda q: True,
        out=out.append,
    )
    return code, "\n".join(out)


def body_of(gh, number):
    return gh.issues[number - 1].body


# --- first run -----------------------------------------------------------------------------


def test_creates_project_fields_issues_and_items(project):
    gh = FakeGitHub()
    code, out = run(project, gh)
    assert code == 0, out

    assert gh.project_title == "demo Roadmap" and gh.linked
    assert {n: [o.name for o in f["options"]] for n, f in gh.fields.items()} == {
        "Status": ["Backlog", "Ready", "In progress", "In review", "Done"],
        "Phase": ["v0.1"],
        "Kind": ["Epic", "Feature", "ADR", "Chore", "Bug", "Docs"],
        "Priority": ["P0", "P1", "P2", "P3"],
        "Size": ["XS", "S", "M", "L", "XL"],
    }
    assert [i.title for i in gh.issues] == ["Title e", "Title a", "Title f"]  # epics first

    assert gh.item_values(3) == {
        "status": "Backlog",
        "phase": "v0.1",
        "kind": "Feature",
        "priority": "P1",
        "size": "M",
    }
    created = {c[1]: c for c in gh.calls_of("issue")}
    assert created["Title f"][2] == "v0.1"  # milestone
    assert created["Title f"][3] == ("type:feature", "P1")


def test_state_records_project_issues_and_items(project):
    gh = FakeGitHub()
    run(project, gh)
    state = load_state(project)
    assert state.get_id("project", "number") == "1"
    assert state.get_id("project", "id") == "PVT_1"
    assert [state.get_id("issues", i) for i in "eaf"] == ["1", "2", "3"]
    assert state.get_id("items", "f") is not None


def test_bodies_have_parent_acceptance_criteria_and_marker(project):
    gh = FakeGitHub()
    run(project, gh)
    child = body_of(gh, 3)
    assert child.startswith("Part of #1.")
    assert "Context here." in child
    assert "## Acceptance criteria\n- [ ] it works" in child
    assert child.rstrip().endswith("<!-- project-kit:id=f -->")


def test_epic_lists_its_children_as_a_checklist(project):
    gh = FakeGitHub()
    run(project, gh)
    epic = body_of(gh, 1)
    assert "## Child issues\n- [ ] #2\n- [ ] #3" in epic
    assert epic.index("children:end") < epic.index("project-kit:id=e")
    assert len(gh.calls_of("edit")) == 1


def test_dry_run_describes_project_and_issues_but_changes_nothing(project):
    gh = FakeGitHub()
    code, out = run(project, gh, dry_run=True)
    assert code == 0
    assert "Project and issues:" in out
    assert "+ project    demo Roadmap" in out and "+ issue      f: Title f" in out
    assert "~ epic       e: list 2 child issue(s)" in out
    assert gh.calls == [] and gh.project is None and gh.issues == []


# --- repeating -----------------------------------------------------------------------------


def test_second_run_changes_nothing(project):
    gh = FakeGitHub()
    run(project, gh)
    gh.calls.clear()
    code, out = run(project, gh)
    assert code == 0 and "Nothing to do." in out
    assert gh.calls == []


def test_cards_the_user_moved_are_never_moved_back(project):
    gh = FakeGitHub()
    run(project, gh)
    gh.set_status(3, "In progress")
    run(project, gh)
    assert gh.item_values(3)["status"] == "In progress"


def test_existing_issues_are_never_rewritten(project):
    gh = FakeGitHub()
    run(project, gh)
    edited = gh.issues[2]
    gh.issues[2] = type(edited)(3, "My own title", "I rewrote this", edited.url)
    gh.calls.clear()
    run(project, gh)
    assert gh.issues[2].body == "I rewrote this" and gh.issues[2].title == "My own title"
    assert gh.calls == []


def test_fields_changed_by_hand_are_not_overwritten(project):
    gh = FakeGitHub()
    run(project, gh)
    field = gh.fields["Priority"]
    gh.items[next(i for i, it in gh.items.items() if it["number"] == 3)]["values"][field["id"]] = (
        next(o.id for o in field["options"] if o.name == "P3")
    )
    run(project, gh)
    assert gh.item_values(3)["priority"] == "P3"


def test_adding_a_child_updates_the_epic_and_keeps_ticked_boxes(project):
    gh = FakeGitHub()
    run(project, gh)
    ticked = body_of(gh, 1).replace("- [ ] #2", "- [x] #2")
    gh.issues[0] = type(gh.issues[0])(1, "Title e", ticked, gh.issues[0].url)

    write_backlog(project, backlog_data(issue("g", parent="e")))
    gh.calls.clear()
    run(project, gh)

    epic = body_of(gh, 1)
    assert "- [x] #2\n- [ ] #3\n- [ ] #4" in epic
    assert [c[1] for c in gh.calls_of("issue")] == ["Title g"]
    assert [c[1] for c in gh.calls_of("edit")] == [1]


def test_issues_are_found_by_marker_when_the_state_is_lost(project):
    gh = FakeGitHub()
    run(project, gh)
    state = load_state(project)
    state.provider_ids.clear()  # keeps the approval, forgets every id
    save_state(project, state)
    gh.calls.clear()
    code, _ = run(project, gh)
    assert code == 0
    assert gh.calls_of("issue") == [] and len(gh.issues) == 3
    assert load_state(project).get_id("issues", "f") == "3"


def test_a_new_phase_adds_an_option_without_losing_existing_values(project):
    gh = FakeGitHub()
    run(project, gh)
    phase_before = {o.name: o.id for o in gh.fields["Phase"]["options"]}

    write_backlog(
        project, backlog_data(issue("g", phase="later", parent="e"), phases=("mvp", "later"))
    )
    run(project, gh)

    phase = {o.name: o.id for o in gh.fields["Phase"]["options"]}
    assert list(phase) == ["v0.1", "v0.2"]
    assert phase["v0.1"] == phase_before["v0.1"]  # same option, so existing items keep it
    assert gh.item_values(3)["phase"] == "v0.1"
    assert gh.item_values(4)["phase"] == "v0.2"


# --- failures and unusual projects ---------------------------------------------------------


def test_failure_while_creating_issues_resumes_without_duplicates(project):
    gh = FakeGitHub(fail_on="issue:Title f")
    code, out = run(project, gh)
    assert code == 1 and "Stopped" in out and "resume" in out
    assert [i.title for i in gh.issues] == ["Title e", "Title a"]
    assert load_state(project).get_id("issues", "a") == "2"

    code, _ = run(project, gh)
    assert code == 0
    assert [i.title for i in gh.issues] == ["Title e", "Title a", "Title f"]
    assert gh.item_values(3)["status"] == "Backlog"
    assert "- [ ] #3" in body_of(gh, 1)


def test_failure_after_creating_issues_resumes_filling_the_project(project):
    gh = FakeGitHub()
    gh.fail_on = None
    run(project, gh)
    for item in gh.items.values():
        item["values"].clear()  # as if the field updates had never happened
    gh.calls.clear()
    code, _ = run(project, gh)
    assert code == 0 and gh.calls_of("issue") == []
    assert gh.item_values(3)["status"] == "Backlog"


def test_a_customised_status_field_is_left_alone_and_reported(project):
    gh = FakeGitHub()
    gh.create_project("o", "demo Roadmap")
    status = gh.fields["Status"]
    status["options"] = [SelectOption(n, id=gh._id("O")) for n in ("Todo", "Doing", "Shipped")]
    gh.calls.clear()

    code, out = run(project, gh)
    assert code == 0
    assert [o.name for o in gh.fields["Status"]["options"]] == ["Todo", "Doing", "Shipped"]
    assert "Status field has no option(s) Backlog" in out
    assert "status" not in gh.item_values(3)  # nothing to set it to, and nothing was invented


def test_status_is_not_replaced_when_the_project_already_has_items(project):
    gh = FakeGitHub()
    gh.create_project("o", "demo Roadmap")
    gh.add_existing_issue("Old card")
    item = gh.add_item("o", gh.project, "https://github.com/o/r/issues/1")
    gh.items[item]["values"][gh.fields["Status"]["id"]] = gh.fields["Status"]["options"][2].id
    gh.calls.clear()

    run(project, gh)
    assert [o.name for o in gh.fields["Status"]["options"]] == ["Todo", "In Progress", "Done"]
    assert gh.item_values(1)["status"] == "Done"  # the existing card keeps its status


def test_labels_for_an_issue_combine_type_priority_and_declared_labels():
    data = backlog_data()
    data["labels"] = [{"name": "area:x"}]
    data["issues"][2]["labels"] = ["area:x"]
    backlog = parse_backlog(json.dumps(data))
    assert issue_labels(backlog.issues[2]) == ["type:feature", "P1", "area:x"]


# --- pure helpers --------------------------------------------------------------------------


def test_children_block_is_inserted_before_the_marker_and_is_stable():
    body = "Intro\n\n<!-- project-kit:id=e -->\n"
    once = with_children_block(body, [4, 5])
    assert once.startswith("Intro\n\n<!-- project-kit:children:start -->")
    assert once.rstrip().endswith("<!-- project-kit:id=e -->")
    assert with_children_block(once, [4, 5]) == once


def test_children_block_without_a_marker_goes_at_the_end():
    assert with_children_block("Just text", [1]).endswith("children:end -->\n")


def test_children_block_keeps_ticks_and_drops_removed_children():
    body = with_children_block("x\n", [1, 2, 3]).replace("- [ ] #2", "- [x] #2")
    updated = with_children_block(body, [2, 3])
    assert "- [x] #2\n- [ ] #3" in updated and "#1" not in updated


def test_body_without_optional_parts_is_just_the_marker():
    backlog = parse_backlog(json.dumps(backlog_data()))
    assert build_body(backlog.issues[0], None) == "<!-- project-kit:id=e -->\n"


# --- the GitHub adapter --------------------------------------------------------------------


class Script:
    def __init__(self, *results):
        self.results = list(results)
        self.cmds = []
        self.inputs = []

    def __call__(self, cmd, **kwargs):
        self.cmds.append(cmd[1:])
        self.inputs.append(kwargs.get("input"))
        code, out, err = self.results.pop(0)
        return subprocess.CompletedProcess(cmd, code, stdout=out, stderr=err)


def provider_with(*results):
    script = Script(*results)
    return GitHubProvider(Gh(retries=0, runner=script, sleep=lambda s: None), "o/r"), script


def ok(data):
    return (0, json.dumps(data), "")


PROJECT = ProjectRef(6, "PVT_6", "https://github.com/users/o/projects/6")


def test_create_issue_sends_the_body_on_stdin_and_parses_the_number():
    provider, script = provider_with((0, "https://github.com/o/r/issues/42\n", ""))
    created = provider.create_issue("T", "Body\nlines", "v0.1", ["a", "b"])
    cmd = script.cmds[0]
    assert cmd[:6] == ["issue", "create", "--repo", "o/r", "--title", "T"]
    assert cmd[6:8] == ["--body-file", "-"]
    assert cmd.count("--label") == 2 and cmd[cmd.index("--milestone") + 1] == "v0.1"
    assert script.inputs[0] == b"Body\nlines"
    assert created.number == 42 and created.url.endswith("/42")


def test_list_issues_exposes_the_local_id_from_the_marker():
    provider, _ = provider_with(
        ok(
            [
                {
                    "number": 1,
                    "title": "A",
                    "body": "x\n<!-- project-kit:id=sign-up -->",
                    "url": "u1",
                },
                {"number": 2, "title": "B", "body": None, "url": "u2"},
            ]
        )
    )
    issues = provider.list_issues()
    assert [i.local_id for i in issues] == ["sign-up", None]


def test_find_project_matches_by_title_and_ignores_closed_ones():
    rows = [
        {"number": 1, "title": "Other", "id": "a", "url": "u"},
        {"number": 2, "title": "demo Roadmap", "id": "b", "url": "u", "closed": True},
        {"number": 3, "title": "demo Roadmap", "id": "c", "url": "u3"},
    ]
    provider, _ = provider_with(ok({"projects": rows}), ok({"projects": rows[:1]}))
    assert provider.find_project("o", "demo Roadmap").number == 3
    assert provider.find_project("o", "demo Roadmap") is None


def test_project_items_parse_field_values_by_lowercase_name():
    provider, _ = provider_with(
        ok(
            {
                "items": [
                    {"id": "I1", "content": {"number": 7}, "status": "Done", "phase": "v0.1"},
                    {"id": "I2", "content": {"type": "DraftIssue"}, "size": "M"},
                ]
            }
        )
    )
    items = provider.project_items("o", PROJECT)
    assert (items[0].number, items[0].values) == (7, {"status": "Done", "phase": "v0.1"})
    assert (items[1].number, items[1].values) == (None, {"size": "M"})


def test_set_item_values_is_one_request_with_variables():
    provider, script = provider_with(ok({"data": {}}))
    provider.set_item_values(PROJECT, "ITEM", {"F1": "O1", "F2": "O2"})
    assert len(script.cmds) == 1 and script.cmds[0] == ["api", "graphql", "--input", "-"]
    payload = json.loads(script.inputs[0])
    assert payload["variables"] == {
        "p": "PVT_6",
        "i": "ITEM",
        "f0": "F1",
        "o0": "O1",
        "f1": "F2",
        "o1": "O2",
    }
    assert payload["query"].count("updateProjectV2ItemFieldValue") == 2
    assert "F1" not in payload["query"]  # ids travel as variables, never inlined


def test_set_item_values_with_nothing_to_set_makes_no_request():
    provider, script = provider_with()
    provider.set_item_values(PROJECT, "ITEM", {})
    assert script.cmds == []


def test_set_select_options_keeps_the_ids_of_existing_options():
    provider, script = provider_with(ok({"data": {}}))
    provider.set_select_options(
        "FIELD", [SelectOption("A", "BLUE", "d", "OPT1"), SelectOption("B")]
    )
    sent = json.loads(script.inputs[0])["variables"]["o"]
    assert sent == [
        {"name": "A", "color": "BLUE", "description": "d", "id": "OPT1"},
        {"name": "B", "color": "GRAY", "description": ""},
    ]


def test_graphql_errors_are_raised():
    provider, _ = provider_with(ok({"errors": [{"message": "nope"}]}))
    with pytest.raises(Exception, match="nope"):
        provider.set_item_values(PROJECT, "I", {"F": "O"})
