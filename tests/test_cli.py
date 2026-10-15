import pytest

from project_kit import __version__
from project_kit.cli import main


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_arguments_prints_the_visual_guide(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "THE FLOW" in out and "IN THE TERMINAL" in out
