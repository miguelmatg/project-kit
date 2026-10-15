import io

from project_kit import installer
from project_kit.cli import build_parser, main
from project_kit.config import Config
from project_kit.help import TERMINAL_COMMANDS, Style, render_help
from project_kit.state import State
from project_kit.workflow import default_workflow


def subcommands():
    parser = build_parser()
    action = next(a for a in parser._actions if a.dest == "command")
    return list(action.choices)


def test_every_subcommand_is_in_the_guide():
    text = " ".join(cmd for cmd, _ in TERMINAL_COMMANDS)
    for name in subcommands():
        assert f"project-kit {name}" in text, name


def test_every_phase_and_skill_is_in_the_guide():
    text = render_help(default_workflow())
    for step in default_workflow().steps:
        assert f"/{step.skill}" in text


def test_plain_style_has_no_escape_codes_and_stays_in_ascii():
    text = render_help(default_workflow(), style=Style(color=False, unicode=False))
    assert "\033" not in text
    text.encode("ascii")


def test_rich_style_uses_colour_and_box_characters():
    text = render_help(default_workflow(), style=Style(color=True, unicode=True))
    assert "\033[" in text and "│" in text and "→" in text


def test_lines_fit_a_narrow_terminal():
    text = render_help(default_workflow(), style=Style(), width=80)
    assert max(len(line) for line in text.splitlines()) <= 80


def test_it_marks_the_progress_of_a_project():
    state = State()
    state.approve("discover")
    text = render_help(default_workflow(), state, "demo", Style())
    assert "(demo)" in text
    assert "[x] discover" in text and "[>] decide" in text
    assert "Next: /pk-decide" in text


def test_outside_a_project_it_shows_the_generic_flow(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["help"]) == 0
    out = capsys.readouterr().out
    assert "FIRST TIME" in out and "[>]" not in out


def test_inside_a_project_it_shows_where_you_are(tmp_path, monkeypatch, capsys):
    installer.init_project(tmp_path, Config(project_name="demo"))
    monkeypatch.chdir(tmp_path)
    assert main(["help"]) == 0
    out = capsys.readouterr().out
    assert "(demo)" in out and "[>] discover" in out and "FIRST TIME" not in out


def test_a_legacy_console_gets_ascii_and_does_not_crash(tmp_path, monkeypatch):
    legacy = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    style = Style.detect(legacy)
    assert not style.unicode and not style.color
    legacy.write(render_help(default_workflow(), style=style))  # would raise on a box character


def test_a_utf8_terminal_gets_box_characters():
    assert Style.detect(io.TextIOWrapper(io.BytesIO(), encoding="utf-8")).unicode
