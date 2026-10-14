""".project-kit/config.yml: project-level settings, versioned with the repo."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from project_kit.fsutil import atomic_write_text

PROJECT_DIR = ".project-kit"
PROVIDERS = ("github", "gitlab")
BRANCH_KEYS = ("main", "release", "develop")


class ConfigError(ValueError):
    """The configuration file is missing, unreadable or invalid."""


def config_path(root: Path) -> Path:
    return root / PROJECT_DIR / "config.yml"


def _default_branches() -> dict[str, str]:
    return {"main": "main", "release": "release", "develop": "develop"}


@dataclass
class Config:
    project_name: str
    provider: str = "github"
    language: str = "en"
    branches: dict[str, str] = field(default_factory=_default_branches)

    def validate(self) -> None:
        problems = []
        if not self.project_name.strip():
            problems.append("project_name must not be empty")
        if self.provider not in PROVIDERS:
            problems.append(
                f"provider must be one of {', '.join(PROVIDERS)}, got {self.provider!r}"
            )
        if not self.language.strip():
            problems.append("language must not be empty")
        if set(self.branches) != set(BRANCH_KEYS):
            problems.append(f"branches must define exactly: {', '.join(BRANCH_KEYS)}")
        else:
            for key, name in self.branches.items():
                if not isinstance(name, str) or not name.strip():
                    problems.append(f"branches.{key} must be a non-empty string")
            names = list(self.branches.values())
            if len(set(names)) != len(names):
                problems.append("branches must use three different names")
        if problems:
            raise ConfigError("Invalid config: " + "; ".join(problems))

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "provider": self.provider,
            "language": self.language,
            "branches": dict(self.branches),
        }


_HEADER = "# project-kit configuration. Safe to edit by hand.\n"


def parse_config(text: str) -> Config:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"config.yml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("config.yml must contain a mapping of settings")

    unknown = set(data) - {"project_name", "provider", "language", "branches"}
    if unknown:
        raise ConfigError(
            f"Unknown setting(s) in config.yml: {', '.join(sorted(map(str, unknown)))}"
        )
    if "project_name" not in data:
        raise ConfigError("config.yml is missing required setting: project_name")

    raw_branches = data.get("branches") or {}
    if not isinstance(raw_branches, dict):
        raise ConfigError("branches must be a mapping (main, release, develop)")
    branches = {**_default_branches(), **raw_branches}
    for key in ("project_name", "provider", "language"):
        if key in data and not isinstance(data[key], str):
            raise ConfigError(f"{key} must be a string")

    config = Config(
        project_name=data["project_name"],
        provider=data.get("provider", "github"),
        language=data.get("language", "en"),
        branches=branches,
    )
    config.validate()
    return config


def load_config(root: Path) -> Config:
    path = config_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"No config found at {path}. Run `project-kit init` first.") from exc
    return parse_config(text)


def save_config(root: Path, config: Config) -> None:
    config.validate()
    body = yaml.safe_dump(config.to_dict(), sort_keys=False, allow_unicode=True)
    atomic_write_text(config_path(root), _HEADER + body)
