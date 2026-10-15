import copy
import json
from pathlib import Path

import pytest
from fakes import approve_through

from project_kit import installer
from project_kit.approval import approve_phase
from project_kit.backlog import (
    Backlog,
    BacklogError,
    Issue,
    Phase,
    backlog_path,
    load_backlog,
    parse_backlog,
    save_backlog,
)
from project_kit.cli import main
from project_kit.config import Config, ConfigError
from project_kit.state import StateError, load_state

EXAMPLE = Path(installer.__file__).parent / "assets/templates/backlog.example.json"


def valid() -> dict:
    return {
        "version": 1,
        "phases": [{"id": "mvp", "title": "v0.1"}],
        "labels": [{"name": "area:x", "color": "0E8A16"}],
        "issues": [
            {
                "id": "e",
                "type": "epic",
                "phase": "mvp",
                "title": "Epic",
                "priority": "P1",
                "size": "L",
            },
            {
                "id": "f",
                "type": "feature",
                "phase": "mvp",
                "title": "Feature",
                "priority": "P2",
                "size": "S",
                "parent": "e",
                "labels": ["area:x"],
                "acceptance": ["it works"],
            },
        ],
    }


def problems_of(data) -> list[str]:
    with pytest.raises(BacklogError) as exc:
        parse_backlog(json.dumps(data))
    return exc.value.problems


def mutated(fn) -> dict:
    data = copy.deepcopy(valid())
    fn(data)
    return data


def test_shipped_example_is_valid():
    backlog = parse_backlog(EXAMPLE.read_text(encoding="utf-8"))
    assert len(backlog.phases) == 2
    assert [i.id for i in backlog.children_of("epic-accounts")] == [
        "adr-auth",
        "sign-up",
        "profile-page",
    ]


def test_valid_backlog_parses_and_roundtrips(tmp_path):
    backlog = parse_backlog(json.dumps(valid()))
    save_backlog(tmp_path, backlog)
    assert load_backlog(tmp_path) == backlog
    assert json.loads(backlog_path(tmp_path).read_text(encoding="utf-8")) == valid()


def test_summary_counts_by_phase_and_priority():
    text = parse_backlog(json.dumps(valid())).summary()
    assert "1 phase(s), 2 issue(s)" in text
    assert "v0.1: 2 (epic: 1, feature: 1)" in text
    assert "P1: 1" in text


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d.update(version=2), "unsupported version"),
        (lambda d: d.update(extra=1), "unknown field 'extra'"),
        (lambda d: d["issues"][0].update(prio="P1"), "unknown field 'prio'"),
        (lambda d: d["issues"][0].pop("title"), "missing required field 'title'"),
        (lambda d: d["issues"][0].update(title="  "), "must not be empty"),
        (lambda d: d["issues"][0].update(type="story"), "'type' must be one of"),
        (lambda d: d["issues"][0].update(priority="P9"), "'priority' must be one of"),
        (lambda d: d["issues"][0].update(size="XXL"), "'size' must be one of"),
        (lambda d: d["issues"][0].update(id="Not Valid"), "lowercase letters"),
        (lambda d: d["issues"][1].update(id="e"), "duplicate id 'e'"),
        (lambda d: d["phases"].append({"id": "mvp", "title": "other"}), "duplicate id 'mvp'"),
        (lambda d: d["phases"].append({"id": "x", "title": "v0.1"}), "duplicate title 'v0.1'"),
        (lambda d: d["issues"][0].update(phase="nope"), "unknown phase 'nope'"),
        (lambda d: d["issues"][1].update(parent="ghost"), "unknown parent 'ghost'"),
        (lambda d: d["issues"][1].update(parent="f"), "not an epic"),
        (lambda d: d["issues"][0].update(parent="f"), "epic cannot have a parent"),
        (lambda d: d["issues"][1].update(acceptance=[]), "needs at least one acceptance"),
        (lambda d: d["issues"][1].update(labels=["typo"]), "not declared in 'labels'"),
        (lambda d: d["issues"][1].update(acceptance="a"), "list of non-empty strings"),
        (lambda d: d["labels"][0].update(color="#fff"), "6 hex digits"),
        (lambda d: d["labels"].append({"name": "area:x"}), "duplicate name 'area:x'"),
        (lambda d: d.update(issues=["x"]), "must be an object"),
    ],
)
def test_each_rule_is_reported(change, expected):
    assert any(expected in p for p in problems_of(mutated(change)))


def test_epic_and_adr_do_not_need_acceptance_criteria():
    data = valid()
    data["issues"].append(
        {"id": "a", "type": "adr", "phase": "mvp", "title": "D", "priority": "P2", "size": "S"}
    )
    parse_backlog(json.dumps(data))  # does not raise


def test_all_problems_are_reported_at_once():
    def many(d):
        d["issues"][0]["priority"] = "P9"
        d["issues"][1]["phase"] = "nope"
        d["issues"][1]["acceptance"] = []

    assert len(problems_of(mutated(many))) == 3


def test_invalid_json_and_wrong_root():
    with pytest.raises(BacklogError, match="not valid JSON"):
        parse_backlog("{oops")
    with pytest.raises(BacklogError, match="must be an object"):
        parse_backlog("[]")


def test_missing_backlog_points_to_the_skill(tmp_path):
    with pytest.raises(BacklogError, match="pk-plan"):
        load_backlog(tmp_path)


def test_save_refuses_invalid_backlog(tmp_path):
    bad = Backlog(
        phases=[Phase("mvp", "v0.1")],
        issues=[Issue("a", "feature", "ghost", "T", "P1", "S")],
    )
    with pytest.raises(BacklogError):
        save_backlog(tmp_path, bad)
    assert not backlog_path(tmp_path).exists()


# --- approval gate and CLI ---------------------------------------------------------------


@pytest.fixture
def project(tmp_path, monkeypatch):
    installer.init_project(tmp_path, Config(project_name="demo"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_backlog(root, data):
    backlog_path(root).write_text(json.dumps(data), encoding="utf-8")


def test_plan_cannot_be_approved_without_a_valid_backlog(project):
    approve_through(project, "workflow")
    with pytest.raises(BacklogError):
        approve_phase(project, "plan")
    write_backlog(project, mutated(lambda d: d["issues"][0].update(priority="P9")))
    with pytest.raises(BacklogError):
        approve_phase(project, "plan")
    assert not load_state(project).is_approved("plan")


def test_approving_plan_records_it_and_advances_the_phase(project):
    write_backlog(project, valid())
    approve_through(project, "workflow")
    state = approve_phase(project, "plan")
    assert state.is_approved("plan") and state.phase == "plan"
    assert load_state(project).is_approved("plan")


def test_approving_an_earlier_phase_does_not_move_the_phase_back(project):
    write_backlog(project, valid())
    approve_through(project, "plan")
    assert approve_phase(project, "discover").phase == "plan"


def test_approve_requires_an_initialised_project(tmp_path):
    with pytest.raises(ConfigError):
        approve_phase(tmp_path, "plan")


def test_approve_unknown_phase(project):
    with pytest.raises(StateError):
        approve_phase(project, "party")


def test_cli_backlog_validate(project, capsys):
    assert main(["backlog", "validate"]) == 1
    assert "pk-plan" in capsys.readouterr().err

    write_backlog(project, valid())
    assert main(["backlog", "validate"]) == 0
    assert "Backlog is valid." in capsys.readouterr().out

    write_backlog(project, mutated(lambda d: d["issues"][0].update(size="XXL")))
    assert main(["backlog", "validate"]) == 1
    assert "'size' must be one of" in capsys.readouterr().err


def test_cli_approve(project, capsys):
    approve_through(project, "workflow")
    assert main(["approve", "plan"]) == 1
    assert "pk-plan" in capsys.readouterr().err
    write_backlog(project, valid())
    assert main(["approve", "plan"]) == 0
    assert "approved" in capsys.readouterr().out
