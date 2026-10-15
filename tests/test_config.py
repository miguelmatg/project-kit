import pytest

from project_kit.config import (
    Config,
    ConfigError,
    config_path,
    load_config,
    parse_config,
    save_config,
)


def test_roundtrip(tmp_path):
    config = Config(
        project_name="demo", language="es", branches={"main": "m", "release": "r", "develop": "d"}
    )
    save_config(tmp_path, config)
    assert load_config(tmp_path) == config
    assert config_path(tmp_path).read_text(encoding="utf-8").startswith("# project-kit")


def test_defaults_applied():
    config = parse_config("project_name: demo\n")
    assert config.provider == "github"
    assert config.language == "en"
    assert config.branches == {"main": "main", "release": "release", "develop": "develop"}


def test_partial_branches_are_completed_with_defaults():
    config = parse_config("project_name: demo\nbranches:\n  develop: dev\n")
    assert config.branches == {"main": "main", "release": "release", "develop": "dev"}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "mapping"),
        ("- a\n- b\n", "mapping"),
        ("provider: github\n", "project_name"),
        ("project_name: ''\n", "must not be empty"),
        ("project_name: demo\nprovider: bitbucket\n", "provider must be one of"),
        ("project_name: demo\nprovidr: github\n", "Unknown setting"),
        ("project_name: demo\nlanguage: 3\n", "must be a string"),
        ("project_name: demo\nbranches: main\n", "branches must be a mapping"),
        ("project_name: demo\nbranches:\n  main: x\n  develop: x\n", "different names"),
        ("project_name: demo\nbranches:\n  hotfix: h\n", "exactly"),
        ("project_name: [unclosed\n", "not valid YAML"),
    ],
)
def test_invalid_configs_are_rejected_with_clear_message(text, message):
    with pytest.raises(ConfigError, match=message):
        parse_config(text)


def test_load_missing_config_points_to_init(tmp_path):
    with pytest.raises(ConfigError, match="project-kit init"):
        load_config(tmp_path)


def test_save_refuses_invalid_config(tmp_path):
    with pytest.raises(ConfigError):
        save_config(tmp_path, Config(project_name="demo", provider="nope"))
    assert not config_path(tmp_path).exists()
