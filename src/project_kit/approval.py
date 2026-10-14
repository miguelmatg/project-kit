"""Approval gates: record that the user signed off on a phase."""

from pathlib import Path

from project_kit.backlog import load_backlog
from project_kit.config import load_config
from project_kit.state import PHASES, State, StateError, load_state, save_state


def approve_phase(root: Path, phase: str) -> State:
    """Record the approval of ``phase`` in the project state.

    The ``plan`` gate refuses to open unless the backlog on disk is valid, so an approval
    always refers to a backlog that provisioning can use.
    """
    if phase not in PHASES:
        raise StateError(f"Unknown phase {phase!r}. Phases: {', '.join(PHASES)}")
    load_config(root)  # the project must have been initialised
    if phase == "plan":
        load_backlog(root)

    state = load_state(root)
    state.approve(phase)
    if PHASES.index(phase) > PHASES.index(state.phase):
        state.phase = phase
    save_state(root, state)
    return state
