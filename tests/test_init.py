from pathlib import Path

import pytest

from project_kit import installer
from project_kit.cli import main
from project_kit.config import Config, ConfigError, load_config
from project_kit.state import load_state

SKILL = Path(".claude/skills/pk-init/SKILL.md")
PR_TEMPLATE = Path(".project-kit/templates/github/pull_request_template.md")


def cfg(**kw):
    return Config(project_name=kw.pop("project_name", "demo"), **kw)


def test_creates_config_state_skills_and_templates(tmp_path):
    report = installer.init_project(tmp_path, cfg(language="es"))

    assert load_config(tmp_path).language == "es"
    assert load_state(tmp_path).phase == "init"
    assert (tmp_path / SKILL).read_text(encoding="utf-8").startswith("---\nname: pk-init")
    assert (tmp_path / PR_TEMPLATE).is_file()
    assert (tmp_path / ".project-kit/templates/github/ISSUE_TEMPLATE/feature.yml").is_file()
    assert Path(".project-kit/config.yml") in report.created
    assert Path(".project-kit/state.json") in report.created
    assert SKILL in report.created
    assert not report.kept and not report.unchanged


def test_every_shipped_asset_is_installed(tmp_path):
    installer.init_project(tmp_path, cfg())
    shipped = list(installer.iter_assets())
    assert len(shipped) >= 7
    for rel, content in shipped:
        assert (tmp_path / rel).read_bytes() == content


def test_second_run_is_a_noop(tmp_path):
    installer.init_project(tmp_path, cfg())
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    report = installer.init_project(tmp_path, cfg())

    assert report.created == [] and report.kept == []
    assert Path(".project-kit/config.yml") in report.unchanged
    assert SKILL in report.unchanged
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_manual_edits_are_never_overwritten(tmp_path):
    installer.init_project(tmp_path, cfg())
    (tmp_path / SKILL).write_text("my own skill", encoding="utf-8")
    (tmp_path / PR_TEMPLATE).write_text("my own template", encoding="utf-8")

    report = installer.init_project(tmp_path, cfg())

    assert (tmp_path / SKILL).read_text(encoding="utf-8") == "my own skill"
    assert (tmp_path / PR_TEMPLATE).read_text(encoding="utf-8") == "my own template"
    assert SKILL in report.kept and PR_TEMPLATE in report.kept


def test_existing_config_wins_over_new_arguments(tmp_path):
    installer.init_project(tmp_path, cfg(project_name="first", language="es"))
    installer.init_project(tmp_path, cfg(project_name="second", language="fr"))
    loaded = load_config(tmp_path)
    assert (loaded.project_name, loaded.language) == ("first", "es")


def test_existing_invalid_config_aborts_before_writing_anything_else(tmp_path):
    (tmp_path / ".project-kit").mkdir()
    (tmp_path / ".project-kit/config.yml").write_text("provider: nope\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        installer.init_project(tmp_path, cfg())
    assert not (tmp_path / ".claude").exists()


def test_missing_file_is_restored_on_rerun(tmp_path):
    installer.init_project(tmp_path, cfg())
    (tmp_path / SKILL).unlink()
    report = installer.init_project(tmp_path, cfg())
    assert report.created == [SKILL]


def test_cli_requires_here(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 2
    assert "--here" in capsys.readouterr().err
    assert not (tmp_path / ".project-kit").exists()


def test_cli_init_here_uses_directory_name_by_default(tmp_path, monkeypatch, capsys):
    project = tmp_path / "my-app"
    project.mkdir()
    monkeypatch.chdir(project)

    assert main(["init", "--here"]) == 0
    assert load_config(project).project_name == "my-app"
    assert "created:" in capsys.readouterr().out

    assert main(["init", "--here"]) == 0
    assert "Nothing to do" in capsys.readouterr().out


def test_cli_reports_invalid_existing_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".project-kit").mkdir()
    (tmp_path / ".project-kit/config.yml").write_text("provider: nope\n", encoding="utf-8")
    assert main(["init", "--here"]) == 1
    assert "project_name" in capsys.readouterr().err
