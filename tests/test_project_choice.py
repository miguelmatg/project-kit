import json

import pytest
from fakes import FakeGitHub, approve_through

from project_kit import installer
from project_kit.backlog import backlog_path
from project_kit.config import Config
from project_kit.project_choice import ProjectChoiceError, Target, resolve_target
from project_kit.providers.github import ProjectRef
from project_kit.provision import run_provision
from project_kit.state import State, load_state

CONFIG = Config(project_name="demo")
BACKLOG = {
    "version": 1,
    "phases": [{"id": "mvp", "title": "v0.1"}],
    "issues": [
        {"id": "e", "type": "epic", "phase": "mvp", "title": "Epic", "priority": "P1", "size": "L"}
    ],
}


def ref(number, title):
    return ProjectRef(
        number, f"PVT_{number}", f"https://github.com/users/o/projects/{number}", title
    )


def world(*projects, linked=None):
    gh = FakeGitHub()
    gh.other_projects = list(projects)
    gh.linked_numbers = {p.number for p in projects} if linked is None else set(linked)
    return gh


def answers(*texts):
    it = iter(texts)
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return next(it)

    ask.asked = asked
    return ask


def resolve(gh, *, state=None, requested=None, interactive=True, assume_yes=False, ask=None):
    return resolve_target(
        gh, "o", CONFIG, state or State(), requested=requested, interactive=interactive,
        assume_yes=assume_yes, ask=ask or answers(), out=lambda _: None,
    )  # fmt: skip


# --- nothing to detect ---------------------------------------------------------------------


def test_with_no_project_it_asks_for_a_name_and_creates_it():
    ask = answers("My board")
    assert resolve(world(), ask=ask) == Target("My board", None, detected=True)
    assert "Name for the new Project [demo Roadmap]" in ask.asked[0]


def test_enter_takes_the_default_name():
    assert resolve(world(), ask=answers("")).title == "demo Roadmap"


def test_with_no_terminal_it_uses_the_default_name_without_asking():
    target = resolve(world(), interactive=False)
    assert target == Target("demo Roadmap", None, detected=True)


# --- one project ---------------------------------------------------------------------------


def test_one_linked_project_is_offered_and_enter_accepts():
    ask = answers("")
    target = resolve(world(ref(10, "Board")), ask=ask)
    assert target == Target("Board", 10, detected=True)
    assert "Use the existing Project Board (#10)" in ask.asked[0]


def test_declining_the_detected_project_asks_for_a_new_name():
    target = resolve(world(ref(10, "Board")), ask=answers("n", "Fresh"))
    assert target == Target("Fresh", None, detected=True)


def test_without_a_terminal_the_only_candidate_is_used():
    assert resolve(world(ref(10, "Board")), interactive=False).number == 10
    assert resolve(world(ref(10, "Board")), assume_yes=True).number == 10


def test_a_project_named_like_the_default_is_found_even_if_not_linked():
    target = resolve(world(ref(11, "demo Roadmap"), linked=[]), interactive=False)
    assert target.number == 11


def test_unlinked_projects_with_other_names_are_not_candidates():
    gh = world(ref(12, "Unrelated"), linked=[])
    assert resolve(gh, interactive=False) == Target("demo Roadmap", None, detected=True)


# --- several projects ----------------------------------------------------------------------


def test_several_projects_are_listed_and_the_user_picks():
    gh = world(ref(10, "One"), ref(11, "Two"))
    ask = answers("2")
    assert resolve(gh, ask=ask).number == 11


def test_several_projects_default_to_the_first_and_can_create_a_new_one():
    gh = world(ref(10, "One"), ref(11, "Two"))
    assert resolve(gh, ask=answers("")).number == 10
    assert resolve(gh, ask=answers("3", "Brand new")) == Target("Brand new", None, detected=True)


def test_an_invalid_choice_is_an_error():
    with pytest.raises(ProjectChoiceError, match="not one of the options"):
        resolve(world(ref(10, "One"), ref(11, "Two")), ask=answers("7"))


def test_several_projects_without_a_terminal_ask_for_the_flag():
    gh = world(ref(10, "One"), ref(11, "Two"))
    with pytest.raises(ProjectChoiceError, match="--project") as exc:
        resolve(gh, interactive=False)
    assert "One" in str(exc.value) and "Two" in str(exc.value)


# --- explicit and remembered ---------------------------------------------------------------


def test_a_remembered_project_is_used_without_looking_or_asking():
    state = State()
    state.set_id("project", "number", "10")
    state.set_id("project", "title", "Board")
    ask = answers()
    assert resolve(world(ref(10, "Board"), ref(11, "Two")), state=state, ask=ask) == Target(
        "Board", 10
    )
    assert ask.asked == []


def test_a_state_from_before_titles_were_stored_uses_the_default_title():
    state = State()
    state.set_id("project", "number", "5")
    assert resolve(world(), state=state) == Target("demo Roadmap", 5)


def test_project_flag_by_number_and_by_title():
    gh = world(ref(10, "One"), ref(11, "Two"), linked=[])
    assert resolve(gh, requested="11", interactive=False).title == "Two"
    assert resolve(gh, requested="One", interactive=False).number == 10


def test_project_flag_with_an_unknown_title_means_create_it():
    assert resolve(world(), requested="Brand new", interactive=False).number is None


def test_project_flag_with_an_unknown_number_is_an_error():
    with pytest.raises(ProjectChoiceError, match="no open Project number 99"):
        resolve(world(), requested="99", interactive=False)


def test_project_flag_beats_what_was_remembered():
    state = State()
    state.set_id("project", "number", "10")
    gh = world(ref(10, "One"), ref(11, "Two"), linked=[])
    assert resolve(gh, state=state, requested="Two", interactive=False).number == 11


# --- through provision ---------------------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    installer.init_project(tmp_path, Config(project_name="demo"))
    backlog_path(tmp_path).write_text(json.dumps(BACKLOG), encoding="utf-8")
    approve_through(tmp_path, "plan")
    return tmp_path


def provision(root, gh, **kw):
    out = []
    code = run_provision(
        root, gh, dry_run=kw.pop("dry_run", False), assume_yes=kw.pop("assume_yes", True),
        confirm=lambda q: True, out=out.append, **kw,
    )  # fmt: skip
    return code, "\n".join(out)


def test_provision_creates_the_project_the_user_named(project):
    gh = FakeGitHub()
    code, out = provision(project, gh, interactive=True, assume_yes=False, ask=answers("Mine"))
    assert code == 0 and gh.project_title == "Mine"
    assert "Project: Mine (new)" in out
    state = load_state(project)
    assert state.get_id("project", "title") == "Mine"


def test_provision_reuses_a_detected_project_instead_of_creating_another(project):
    gh = world(ref(10, "Board"))
    code, out = provision(project, gh, interactive=True, assume_yes=False, ask=answers(""))
    assert code == 0 and "Project: Board (#10, already exists)" in out
    assert not any(c[0] == "create_project" for c in gh.calls)
    assert load_state(project).get_id("project", "number") == "10"


def test_provision_with_several_projects_and_no_terminal_stops_before_changing_anything(project):
    gh = world(ref(10, "One"), ref(11, "Two"))
    code, out = provision(project, gh)
    assert code == 1 and "--project" in out
    assert gh.calls == []


def test_the_choice_is_not_saved_by_a_dry_run(project):
    gh = FakeGitHub()
    code, _ = provision(project, gh, dry_run=True, project="Mine")
    assert code == 0 and gh.calls == []
    assert load_state(project).get_id("project", "title") is None


def test_the_second_run_reuses_what_the_first_one_chose(project):
    gh = FakeGitHub()
    provision(project, gh, project="Mine")
    ask = answers()
    code, _ = provision(project, gh, interactive=True, assume_yes=False, ask=ask)
    assert code == 0 and ask.asked == []
    assert sum(1 for c in gh.calls if c[0] == "create_project") == 1
