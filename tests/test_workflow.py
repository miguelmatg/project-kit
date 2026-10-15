import pytest

from project_kit import installer
from project_kit.approval import approve_phase
from project_kit.cli import main
from project_kit.config import Config
from project_kit.state import PHASES, StateError
from project_kit.workflow import (
    WorkflowError,
    default_workflow,
    load_workflow,
    parse_workflow,
    workflow_path,
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    installer.init_project(tmp_path, Config(project_name="demo"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def edit(project, old, new):
    path = workflow_path(project)
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def test_the_shipped_workflow_covers_every_phase_in_order():
    assert [s.id for s in default_workflow().steps] == list(PHASES)


def test_init_installs_the_workflow_and_the_skills_it_names(project):
    workflow = load_workflow(project)
    assert workflow_path(project).is_file()
    for step in workflow.steps:
        assert (project / ".claude/skills" / step.skill / "SKILL.md").is_file(), step.skill


def test_a_project_without_workflow_file_uses_the_shipped_one(tmp_path):
    assert [s.id for s in load_workflow(tmp_path).steps] == list(PHASES)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("steps: []\n", "schema_version"),
        ('schema_version: "1.0"\nsteps: []\n', "non-empty"),
        ('schema_version: "1.0"\nsteps: [{id: party, title: t, skill: s}]\n', "id must be one of"),
        ('schema_version: "1.0"\nsteps: [{id: plan, title: t, skill: s, gate: maybe}]\n', "gate"),
        ('schema_version: "1.0"\nsteps: [{id: plan, title: t, skill: s, color: red}]\n', "unknown"),
        (
            'schema_version: "1.0"\nsteps: [{id: plan, title: t, skill: s}, '
            "{id: discover, title: t, skill: s}]\n",
            "order",
        ),
        ("- not a mapping\n", "mapping"),
    ],
)
def test_invalid_workflows_are_rejected(text, message):
    with pytest.raises(WorkflowError, match=message):
        parse_workflow(text)


def test_status_starts_at_discover(project, capsys):
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "[x] init" in out and "[>] discover" in out and "Next: /pk-discover" in out


def test_status_follows_the_approvals(project, capsys):
    approve_phase(project, "discover")
    main(["status"])
    out = capsys.readouterr().out
    assert "[x] discover" in out and "[>] decide" in out


def test_status_needs_an_initialised_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["status"]) == 1
    assert "status" in capsys.readouterr().err


def test_the_plan_cannot_be_approved_before_the_brief(project):
    with pytest.raises(StateError, match="discover"):
        approve_phase(project, "decide")


def test_a_disabled_step_no_longer_blocks_later_gates(project, capsys):
    edit(project, "id: decide\n    title", "id: decide\n    enabled: false\n    title")
    approve_phase(project, "discover")
    assert approve_phase(project, "workflow").is_approved("workflow")
    main(["status"])
    assert "[-] decide" in capsys.readouterr().out


def test_the_error_names_how_to_skip_a_phase(project):
    with pytest.raises(StateError, match="enabled: false"):
        approve_phase(project, "workflow")


def test_every_skill_has_matching_frontmatter_and_its_templates_exist(project):
    import re

    for skill_dir in sorted((project / ".claude/skills").iterdir()):
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith(f"---\nname: {skill_dir.name}\n"), skill_dir.name
        for ref in re.findall(r"\.project-kit/templates/[\w./-]+\.(?:md|json)", text):
            assert (project / ref).is_file(), f"{skill_dir.name} mentions missing {ref}"


def test_approving_out_of_order_names_the_missing_phase_even_without_a_backlog(project, capsys):
    assert main(["approve", "plan"]) == 1
    err = capsys.readouterr().err
    assert "discover" in err and "pk-discover" in err
