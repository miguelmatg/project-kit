""".project-kit/config.yml: project-level settings, versioned with the repo."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from project_kit.agents import AGENT_IDS
from project_kit.fsutil import atomic_write_text

PROJECT_DIR = ".project-kit"
PROVIDERS = ("github", "gitlab")
BRANCH_KEYS = ("main", "release", "develop")
MERGE_STRATEGIES = ("squash", "merge", "rebase")
DEFAULT_SPEC_BRANCH = "NNN-name"


class ConfigError(ValueError):
    """The configuration file is missing, unreadable or invalid."""


def config_path(root: Path) -> Path:
    return root / PROJECT_DIR / "config.yml"


def _default_branches() -> dict[str, str]:
    return {"main": "main", "release": "release", "develop": "develop"}


def _default_merge() -> dict[str, str]:
    return {"main": "merge", "release": "merge", "develop": "squash"}


@dataclass
class Config:
    project_name: str
    provider: str = "github"
    language: str = "en"
    branches: dict[str, str] = field(default_factory=_default_branches)
    # False: AI assistants must not appear as co-authors of commits and pull requests.
    ai_coauthor: bool = True
    # The AI agent that guides the phases (see agents.py); empty until one is chosen.
    agent: str = ""
    # How the team works, as data the constitution is generated from (pk-workflow sets it):
    # the name pattern of a spec's branch, and how pull requests are merged into each branch.
    spec_branch: str = DEFAULT_SPEC_BRANCH
    merge: dict[str, str] = field(default_factory=_default_merge)

    def validate(self) -> None:
        problems = []
        if not self.project_name.strip():
            problems.append("project_name must not be empty")
        if self.provider not in PROVIDERS:
            problems.append(
                f"provider must be one of {', '.join(PROVIDERS)}, got {self.provider!r}"
            )
        if self.agent and self.agent not in AGENT_IDS:
            problems.append(f"agent must be one of {', '.join(AGENT_IDS)}, got {self.agent!r}")
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
        if not self.spec_branch.strip() or any(ch.isspace() for ch in self.spec_branch):
            problems.append("workflow.spec_branch must be a pattern without spaces, e.g. NNN-name")
        if set(self.merge) != set(BRANCH_KEYS):
            problems.append(f"workflow.merge must define exactly: {', '.join(BRANCH_KEYS)}")
        else:
            for key, how in self.merge.items():
                if how not in MERGE_STRATEGIES:
                    problems.append(
                        f"workflow.merge.{key} must be one of {', '.join(MERGE_STRATEGIES)}, "
                        f"got {how!r}"
                    )
        if problems:
            raise ConfigError("Invalid config: " + "; ".join(problems))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "project_name": self.project_name,
            "provider": self.provider,
            "language": self.language,
            "branches": dict(self.branches),
            "ai_coauthor": self.ai_coauthor,
            "workflow": {"spec_branch": self.spec_branch, "merge": dict(self.merge)},
        }
        if self.agent:
            data["agent"] = self.agent
        return data


_HEADER = "# project-kit configuration. Safe to edit by hand.\n"


def parse_config(text: str) -> Config:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"config.yml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("config.yml must contain a mapping of settings")

    unknown = set(data) - {
        "project_name",
        "provider",
        "language",
        "branches",
        "ai_coauthor",
        "agent",
        "workflow",
    }
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
    for key in ("project_name", "provider", "language", "agent"):
        if key in data and not isinstance(data[key], str):
            raise ConfigError(f"{key} must be a string")

    workflow = data.get("workflow") or {}
    if not isinstance(workflow, dict):
        raise ConfigError("workflow must be a mapping (spec_branch, merge)")
    extra = set(workflow) - {"spec_branch", "merge"}
    if extra:
        raise ConfigError(f"Unknown setting(s) in workflow: {', '.join(sorted(map(str, extra)))}")
    raw_merge = workflow.get("merge") or {}
    if not isinstance(raw_merge, dict):
        raise ConfigError("workflow.merge must be a mapping (main, release, develop)")
    spec_branch = workflow.get("spec_branch", DEFAULT_SPEC_BRANCH)
    if not isinstance(spec_branch, str):
        raise ConfigError("workflow.spec_branch must be a string")

    ai_coauthor = data.get("ai_coauthor", True)
    if not isinstance(ai_coauthor, bool):
        raise ConfigError("ai_coauthor must be true or false")

    config = Config(
        project_name=data["project_name"],
        provider=data.get("provider", "github"),
        language=data.get("language", "en"),
        branches=branches,
        ai_coauthor=ai_coauthor,
        agent=data.get("agent", ""),
        spec_branch=spec_branch,
        merge={**_default_merge(), **raw_merge},
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
