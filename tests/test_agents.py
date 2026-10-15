import sys

import pytest

from project_kit import agents, cli
from project_kit.config import Config, ConfigError, load_config, parse_config

CLAUDE = agents.get_agent("claude")


def answers(*texts):
    it = iter(texts)

    def ask(_prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return ask


def test_the_list_shows_claude_code_and_a_way_out():
    shown = []
    agents.choose(answers(""), shown.append)
    assert any("1) Claude Code" in line for line in shown)
    assert any("No, I will do it myself" in line for line in shown)


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("", CLAUDE), ("1", CLAUDE), ("2", None), ("9", None), ("claude", None)],
)
def test_choose(typed, expected):
    assert agents.choose(answers(typed), lambda _: None) == expected


def test_no_terminal_means_no_choice():
    assert agents.choose(answers(), lambda _: None) is None


def test_launch_runs_the_agent_in_the_project_with_its_entry_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(agents.shutil, "which", lambda name: f"/bin/{name}")
    calls = []

    class Done:
        returncode = 3

    def run(cmd, **kw):
        calls.append((cmd, kw))
        return Done()

    assert agents.launch(CLAUDE, tmp_path, run) == 3
    assert calls == [(["/bin/claude", "/pk-start"], {"cwd": tmp_path, "check": False})]


def test_launch_without_the_executable_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(agents.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError):
        agents.launch(CLAUDE, tmp_path)


def test_inside_detection():
    assert agents.is_inside(CLAUDE, {"CLAUDECODE": "1"})
    assert not agents.is_inside(CLAUDE, {})


def test_config_remembers_and_validates_the_agent():
    assert parse_config("project_name: x\nagent: claude\n").agent == "claude"
    with pytest.raises(ConfigError, match="agent must be one of"):
        parse_config("project_name: x\nagent: hal9000\n")
    assert "agent" not in Config(project_name="x").to_dict()


@pytest.fixture
def init_env(tmp_path, monkeypatch):
    """A directory where init can run, with no agent running and `claude` installed."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setattr(agents.shutil, "which", lambda name: f"/bin/{name}")
    started = []
    monkeypatch.setattr(agents, "launch", lambda agent, root: started.append((agent.id, root)) or 0)
    return tmp_path, started


def test_init_with_agent_opens_it_and_remembers_it(init_env, capsys):
    root, started = init_env
    assert cli.main(["init", "--agent", "claude"]) == 0
    assert started == [("claude", root)]
    assert load_config(root).agent == "claude"
    out = capsys.readouterr().out
    assert "Starting Claude Code with /pk-start" in out
    assert "Next: open Claude Code" not in out  # no need to repeat what just happened


def test_init_agent_none_never_launches(init_env, capsys):
    _, started = init_env
    assert cli.main(["init", "--agent", "none"]) == 0
    assert started == []
    assert "/pk-start" in capsys.readouterr().out


def test_init_without_a_terminal_never_launches(init_env):
    _, started = init_env
    assert cli.main(["init"]) == 0  # pytest has no tty
    assert started == []


def test_init_with_a_terminal_asks_and_enter_launches(init_env, monkeypatch):
    root, started = init_env
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert cli.main(["init", "--ai-coauthor", "keep"]) == 0
    assert started == [("claude", root)]


def test_init_with_a_terminal_can_decline(init_env, monkeypatch, capsys):
    _, started = init_env
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    assert cli.main(["init", "--ai-coauthor", "keep"]) == 0
    assert started == [] and "/pk-start" in capsys.readouterr().out


def test_init_inside_claude_code_does_not_nest_another_one(init_env, monkeypatch, capsys):
    _, started = init_env
    monkeypatch.setenv("CLAUDECODE", "1")
    assert cli.main(["init", "--agent", "claude"]) == 0
    assert started == []
    assert "already inside Claude Code" in capsys.readouterr().out


def test_init_says_how_to_install_a_missing_agent(init_env, monkeypatch, capsys):
    _, started = init_env
    monkeypatch.setattr(agents.shutil, "which", lambda name: None)
    assert cli.main(["init", "--agent", "claude"]) == 0
    out = capsys.readouterr().out
    assert started == [] and "not found on your PATH" in out and "/pk-start" in out


def test_rerunning_init_does_not_rewrite_the_config_when_the_agent_is_known(init_env):
    root, _ = init_env
    cli.main(["init", "--agent", "claude"])
    before = (root / ".project-kit/config.yml").read_bytes()
    cli.main(["init", "--agent", "claude"])
    assert (root / ".project-kit/config.yml").read_bytes() == before
