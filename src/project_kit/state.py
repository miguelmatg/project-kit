""".project-kit/state.json: where the project is and what exists in the provider.

The ``provider_ids`` map (``kind -> local_id -> provider_id``) is what makes provisioning
resumable: after a partial failure, items already created are looked up here instead of
being created again.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from project_kit.config import PROJECT_DIR
from project_kit.fsutil import atomic_write_text

STATE_VERSION = 1
PHASES = ("init", "discover", "decide", "workflow", "plan", "provision", "handoff")


class StateError(ValueError):
    """The state file is unreadable or invalid."""


def state_path(root: Path) -> Path:
    return root / PROJECT_DIR / "state.json"


@dataclass
class State:
    phase: str = "init"
    approvals: dict[str, str] = field(default_factory=dict)
    provider_ids: dict[str, dict[str, str]] = field(default_factory=dict)

    def validate(self) -> None:
        problems = []
        if self.phase not in PHASES:
            problems.append(f"phase must be one of {', '.join(PHASES)}, got {self.phase!r}")
        for phase, when in self.approvals.items():
            if phase not in PHASES:
                problems.append(f"approvals has unknown phase {phase!r}")
            if not isinstance(when, str):
                problems.append(f"approvals.{phase} must be a timestamp string")
        for kind, ids in self.provider_ids.items():
            if not isinstance(ids, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in ids.items()
            ):
                problems.append(f"provider_ids.{kind} must map local ids to provider ids (strings)")
        if problems:
            raise StateError("Invalid state: " + "; ".join(problems))

    def approve(self, phase: str, when: datetime | None = None) -> None:
        if phase not in PHASES:
            raise StateError(f"Unknown phase {phase!r}")
        self.approvals[phase] = (when or datetime.now(UTC)).isoformat(timespec="seconds")

    def is_approved(self, phase: str) -> bool:
        return phase in self.approvals

    def set_id(self, kind: str, local_id: str, provider_id: str) -> None:
        self.provider_ids.setdefault(kind, {})[local_id] = provider_id

    def get_id(self, kind: str, local_id: str) -> str | None:
        return self.provider_ids.get(kind, {}).get(local_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "phase": self.phase,
            "approvals": self.approvals,
            "provider_ids": self.provider_ids,
        }


def parse_state(text: str) -> State:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StateError(
            f"state.json is not valid JSON ({exc}). It is written atomically, so it was "
            "probably edited by hand; fix or delete it."
        ) from exc
    if not isinstance(data, dict):
        raise StateError("state.json must contain an object")

    version = data.get("version")
    if version != STATE_VERSION:
        hint = (
            " Upgrade project-kit." if isinstance(version, int) and version > STATE_VERSION else ""
        )
        raise StateError(f"Unsupported state.json version {version!r}.{hint}")

    state = State(
        phase=data.get("phase", "init"),
        approvals=data.get("approvals", {}),
        provider_ids=data.get("provider_ids", {}),
    )
    state.validate()
    return state


def load_state(root: Path) -> State:
    """Load the state, or a fresh one if the project has none yet."""
    try:
        text = state_path(root).read_text(encoding="utf-8")
    except FileNotFoundError:
        return State()
    return parse_state(text)


def save_state(root: Path, state: State) -> None:
    state.validate()
    atomic_write_text(
        state_path(root), json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    )
