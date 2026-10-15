import os
import subprocess
import sys

import pytest
from fakes import FakeGitHub, approve_through

from project_kit import installer
from project_kit.approval import approve_phase
from project_kit.cli import main
from project_kit.config import Config, ConfigError, load_config, parse_config, save_config
from project_kit.handoff import (
    CONSTITUTION,
    EXTRA_FILE,
    INPUT_FILE,
    build_constitution_input,
    constitution_ready,
    finish_handoff,
    merge_summary,
    rules_index,
    run_handoff,
)
from project_kit.project_choice import ProjectChoiceError, resolve_target
from project_kit.provision import run_provision
from project_kit.state import State, StateError, load_state

REAL = "# demo Constitution\n\n## Core Principles\n\nEvery spec MUST have a test.\n"
TEMPLATE = "# [PROJECT_NAME] Constitution\n\n### [PRINCIPLE_1_NAME]\n[PRINCIPLE_1_DESCRIPTION]\n"


@pytest.fixture
def project(tmp_path, monkeypatch):
    installer.init_project(tmp_path, Config(project_name="demo"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def plan_ready(root):
    """A valid backlog and every gate up to the plan approved."""
    write(
        root,
        ".project-kit/backlog.json",
        '{"version": 1, "phases": [{"id": "mvp", "title": "v0.1"}], "issues": []}',
    )
    approve_through(root, "plan")


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- the workflow lives in the config, not in the template ---------------------------------


def test_defaults_match_what_the_template_used_to_say():
    cfg = Config(project_name="x")
    assert cfg.spec_branch == "NNN-name"
    assert cfg.merge == {"main": "merge", "release": "merge", "develop": "squash"}


def test_workflow_settings_round_trip(tmp_path):
    cfg = Config(
        project_name="x", spec_branch="spec/<name>", merge={**Config("x").merge, "develop": "merge"}
    )
    save_config(tmp_path, cfg)
    loaded = load_config(tmp_path)
    assert loaded.spec_branch == "spec/<name>" and loaded.merge["develop"] == "merge"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("project_name: x\nworkflow: nope\n", "workflow must be a mapping"),
        ("project_name: x\nworkflow: {color: red}\n", "Unknown setting"),
        ("project_name: x\nworkflow: {merge: {develop: yolo}}\n", "must be one of squash"),
        ("project_name: x\nworkflow: {merge: {staging: merge}}\n", "exactly"),
        ("project_name: x\nworkflow: {spec_branch: 'a b'}\n", "without spaces"),
        ("project_name: x\nworkflow: {spec_branch: 3}\n", "must be a string"),
    ],
)
def test_invalid_workflow_settings(text, message):
    with pytest.raises(ConfigError, match=message):
        parse_config(text)


def test_partial_merge_settings_keep_the_other_defaults():
    cfg = parse_config("project_name: x\nworkflow: {merge: {develop: rebase}}\n")
    assert cfg.merge == {"main": "merge", "release": "merge", "develop": "rebase"}


def test_the_default_summary_is_the_old_sentence():
    assert (
        merge_summary(Config("x"))
        == "Squash merge into `develop`; merge commit into `release` and `main`."
    )


def test_the_summary_follows_the_config():
    cfg = Config("x", merge={"main": "merge", "release": "merge", "develop": "merge"})
    assert merge_summary(cfg) == "Merge commit into `develop`, `release` and `main`."


def test_the_constitution_input_uses_the_branch_pattern_and_merge_strategy(project):
    cfg = Config(
        "demo",
        spec_branch="spec/<name>",
        merge={"main": "merge", "release": "merge", "develop": "merge"},
    )
    text = build_constitution_input(project, cfg)
    assert "`spec/<name>`" in text and "Merge commit into `develop`, `release` and `main`." in text
    assert "NNN-name`, created" not in text and "Squash merge" not in text


# --- the index of rules -------------------------------------------------------------------


def test_the_index_points_to_the_github_project_for_tasks(project):
    state = State()
    state.set_id("project", "title", "demo Roadmap")
    state.set_id("project", "number", "7")
    state.set_id("project", "url", "https://github.com/users/o/projects/7")
    text = rules_index(project, state)
    assert 'GitHub Project "demo Roadmap" (https://github.com/users/o/projects/7)' in text
    assert "One issue is one spec" in text and "Do not keep a parallel task list" in text
    assert "In progress" in text and "In review" in text and "Done" in text


def test_the_index_only_lists_sources_that_exist(project):
    bare = rules_index(project, State())
    assert "Tasks and tracking" not in bare and "brief.md" not in bare

    write(project, "docs/project/brief.md", "# Brief")
    write(project, "docs/development-workflow.md", "# Flow")
    write(project, "docs/adr/0001-x.md", "# ADR")
    write(project, ".github/pull_request_template.md", "x")
    write(project, ".project-kit/backlog.json", "{}")
    full = rules_index(project, State())
    for expected in (
        "docs/project/brief.md",
        "docs/development-workflow.md",
        "`docs/adr/`",
        "pull request template",
        "backlog.json",
    ):
        assert expected in full


def test_the_index_is_in_the_generated_input(project):
    write(project, "docs/development-workflow.md", "# Flow")
    text = build_constitution_input(project, load_config(project))
    assert "## Where the project's rules live" in text and "docs/development-workflow.md" in text


def test_provision_records_the_project_title_and_url_for_the_index(project):
    import json

    from project_kit.backlog import backlog_path

    backlog_path(project).write_text(
        json.dumps(
            {
                "version": 1,
                "phases": [{"id": "mvp", "title": "v0.1"}],
                "issues": [
                    {
                        "id": "e",
                        "type": "epic",
                        "phase": "mvp",
                        "title": "E",
                        "priority": "P1",
                        "size": "L",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    approve_through(project, "plan")
    gh = FakeGitHub()
    run_provision(
        project, gh, dry_run=False, assume_yes=True, confirm=lambda q: True, out=lambda _: None
    )
    state = load_state(project)
    assert state.get_id("project", "title") == "demo Roadmap"
    assert state.get_id("project", "url") == "https://github.com/users/o/projects/1"


# --- the temporary files ------------------------------------------------------------------


def test_the_template_constitution_is_not_ready_and_a_written_one_is(project):
    assert not constitution_ready(project)
    write(project, CONSTITUTION, TEMPLATE)
    assert not constitution_ready(project)
    write(project, CONSTITUTION, "")
    assert not constitution_ready(project)
    write(project, CONSTITUTION, REAL)
    assert constitution_ready(project)


def test_handoff_cannot_be_approved_without_a_written_constitution(project):
    plan_ready(project)
    with pytest.raises(StateError, match="constitution is not written yet"):
        approve_phase(project, "handoff")
    write(project, CONSTITUTION, TEMPLATE)
    with pytest.raises(StateError, match="still the template"):
        approve_phase(project, "handoff")


def approve_all_but_handoff(project):
    plan_ready(project)
    write(project, CONSTITUTION, REAL)


def test_approving_the_handoff_deletes_the_temporary_files(project, capsys):
    approve_all_but_handoff(project)
    write(project, INPUT_FILE, "<!-- project-kit:managed -->\n# input")
    write(project, EXTRA_FILE, "- my rule")
    assert main(["approve", "handoff"]) == 0
    out = capsys.readouterr().out
    assert not (project / INPUT_FILE).exists() and not (project / EXTRA_FILE).exists()
    assert INPUT_FILE.as_posix() in out and "Removed" in out
    assert (project / CONSTITUTION).read_text(encoding="utf-8") == REAL  # never touched


def test_finishing_with_nothing_to_delete_is_fine(project):
    assert finish_handoff(project) == []


def test_after_the_handoff_a_rerun_does_not_bring_the_input_back(project):
    approve_all_but_handoff(project)
    approve_phase(project, "handoff")
    out = []
    code = run_handoff(
        project,
        install=False,
        assume_yes=True,
        dry_run=False,
        confirm=lambda q: True,
        out=out.append,
        which=lambda name: None,
    )
    assert code == 0 and "already done" in "\n".join(out)
    assert not (project / INPUT_FILE).exists()


def test_before_the_handoff_the_input_is_generated_as_usual(project):
    out = []
    run_handoff(
        project,
        install=False,
        assume_yes=True,
        dry_run=False,
        confirm=lambda q: True,
        out=out.append,
        which=lambda name: None,
    )
    assert (project / INPUT_FILE).is_file()


# --- no terminal ---------------------------------------------------------------------------


def test_a_terminal_that_cannot_answer_asks_for_the_flag_instead_of_crashing():
    gh = FakeGitHub()
    gh.other_projects = []

    def eof(_prompt):
        raise EOFError

    with pytest.raises(ProjectChoiceError, match="--project"):
        resolve_target(
            gh, "o", Config("demo"), State(), requested=None, interactive=True,
            assume_yes=False, ask=eof, out=lambda _: None,
        )  # fmt: skip


def test_provision_reports_it_and_changes_nothing(project):
    import json

    from project_kit.backlog import backlog_path

    backlog_path(project).write_text(
        json.dumps({"version": 1, "phases": [{"id": "mvp", "title": "v0.1"}], "issues": []}),
        encoding="utf-8",
    )
    approve_through(project, "plan")
    gh = FakeGitHub()
    out = []

    def eof(_prompt):
        raise EOFError

    code = run_provision(
        project, gh, dry_run=False, assume_yes=False, confirm=lambda q: True, out=out.append,
        interactive=True, ask=eof,
    )  # fmt: skip
    assert code == 1 and "--project" in "\n".join(out) and "Traceback" not in "\n".join(out)
    assert not any(c[0] == "create_project" for c in gh.calls)


# --- accents on a console that is not UTF-8 -------------------------------------------------


def test_accents_survive_a_piped_output_on_any_platform(tmp_path):
    installer.init_project(tmp_path, Config(project_name="Código y Publicación"))
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    result = subprocess.run(
        [sys.executable, "-m", "project_kit", "status"],
        cwd=tmp_path, env=env, capture_output=True,
    )  # fmt: skip
    assert result.returncode == 0
    assert "Código y Publicación".encode() in result.stdout


def test_an_old_template_copy_gets_a_warning_and_a_current_one_does_not(project):
    def run():
        out = []
        run_handoff(
            project, install=False, assume_yes=True, dry_run=True,
            confirm=lambda q: True, out=out.append, which=lambda name: None,
        )  # fmt: skip
        return "\n".join(out)

    assert "older project-kit" not in run()  # the copy init installed is current
    write(project, ".project-kit/templates/constitution-input.md", "# old {{project_name}}")
    assert "older project-kit" in run()
