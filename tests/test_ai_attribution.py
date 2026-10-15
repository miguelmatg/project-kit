import json
import shutil
import subprocess

import pytest

from project_kit import ai_attribution, installer
from project_kit.cli import main
from project_kit.config import Config, ConfigError, load_config, parse_config

SETTINGS = ".claude/settings.json"
HOOK = ".githooks/commit-msg"


def cfg(**kw):
    return Config(project_name="demo", **kw)


def test_by_default_nothing_about_attribution_is_touched(tmp_path):
    installer.init_project(tmp_path, cfg())
    assert not (tmp_path / SETTINGS).exists()
    assert not (tmp_path / HOOK).exists()
    assert load_config(tmp_path).ai_coauthor is True


def test_removing_the_coauthor_configures_claude_and_installs_the_hook(tmp_path):
    report = installer.init_project(tmp_path, cfg(ai_coauthor=False))

    settings = json.loads((tmp_path / SETTINGS).read_text(encoding="utf-8"))
    assert settings["attribution"] == {"commit": "", "pr": ""}
    assert (tmp_path / HOOK).read_text(encoding="utf-8").startswith("#!/bin/sh")
    assert load_config(tmp_path).ai_coauthor is False
    assert ai_attribution.CLAUDE_SETTINGS in report.created
    assert any(ai_attribution.HOOKS_PATH_COMMAND in n for n in report.notes)


def test_existing_claude_settings_are_merged_not_replaced(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / SETTINGS).write_text(
        json.dumps({"theme": "dark", "attribution": {"sessionUrl": False}}), encoding="utf-8"
    )
    installer.init_project(tmp_path, cfg(ai_coauthor=False))

    settings = json.loads((tmp_path / SETTINGS).read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert settings["attribution"] == {"sessionUrl": False, "commit": "", "pr": ""}


def test_invalid_claude_settings_are_left_alone_with_a_note(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / SETTINGS).write_text("{not json", encoding="utf-8")
    report = installer.init_project(tmp_path, cfg(ai_coauthor=False))

    assert (tmp_path / SETTINGS).read_text(encoding="utf-8") == "{not json"
    assert any("not valid JSON" in n for n in report.notes)


def test_rerunning_changes_nothing_and_never_overwrites_the_hook(tmp_path):
    installer.init_project(tmp_path, cfg(ai_coauthor=False))
    (tmp_path / HOOK).write_text("#!/bin/sh\n# mine\n", encoding="utf-8")
    before = (tmp_path / SETTINGS).read_bytes()

    report = installer.init_project(tmp_path, cfg(ai_coauthor=False))

    assert (tmp_path / HOOK).read_text(encoding="utf-8") == "#!/bin/sh\n# mine\n"
    assert (tmp_path / SETTINGS).read_bytes() == before
    assert ai_attribution.CLAUDE_SETTINGS not in report.created


def test_no_reminder_once_git_uses_the_hooks_directory(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/config").write_text("[core]\n\thooksPath = .githooks\n", encoding="utf-8")
    report = installer.init_project(tmp_path, cfg(ai_coauthor=False))
    assert report.notes == []


def test_config_validates_the_flag():
    assert parse_config("project_name: x\nai_coauthor: false\n").ai_coauthor is False
    with pytest.raises(ConfigError, match="ai_coauthor"):
        parse_config("project_name: x\nai_coauthor: maybe\n")


def test_cli_flag_remove(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--ai-coauthor", "remove"]) == 0
    assert load_config(tmp_path).ai_coauthor is False
    assert "core.hooksPath" in capsys.readouterr().out


def test_cli_flag_keep_and_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--ai-coauthor", "keep"]) == 0
    assert load_config(tmp_path).ai_coauthor is True


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_the_hook_strips_ai_trailers_and_keeps_human_ones(tmp_path):
    installer.init_project(tmp_path, cfg(ai_coauthor=False))
    message = tmp_path / "MSG"
    message.write_text(
        "feat: add thing\n\nBody stays.\n\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        "Co-authored-by: GitHub Copilot <copilot@github.com>\n"
        "Co-authored-by: Ana Perez <ana@example.com>\n"
        "Generated with [Claude Code](https://claude.com/claude-code)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["sh", str(tmp_path / HOOK), str(message)], capture_output=True, text=True
    )
    assert result.returncode == 0
    text = message.read_text(encoding="utf-8")
    assert "Body stays." in text and "Ana Perez" in text
    assert "Claude" not in text and "Copilot" not in text


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_the_hook_accepts_a_message_that_becomes_empty(tmp_path):
    installer.init_project(tmp_path, cfg(ai_coauthor=False))
    message = tmp_path / "MSG"
    message.write_text("Co-authored-by: Claude <noreply@anthropic.com>\n", encoding="utf-8")
    result = subprocess.run(["sh", str(tmp_path / HOOK), str(message)], capture_output=True)
    assert result.returncode == 0 and message.read_text(encoding="utf-8") == ""
