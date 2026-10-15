"""Approval gates: record that the user signed off on a phase."""

from pathlib import Path

from project_kit.backlog import load_backlog
from project_kit.config import load_config
from project_kit.handoff import CONSTITUTION, INPUT_FILE, constitution_ready
from project_kit.state import PHASES, State, StateError, load_state, save_state
from project_kit.workflow import load_workflow


def approve_phase(root: Path, phase: str) -> State:
    """Record the approval of ``phase`` in the project state.

    A gate refuses to open while an earlier enabled gate of ``workflow.yml`` is still open,
    so the plan cannot be approved before the brief. The ``plan`` gate also refuses to open
    unless the backlog on disk is valid, so an approval always refers to a backlog that
    provisioning can use.
    """
    if phase not in PHASES:
        raise StateError(f"Unknown phase {phase!r}. Phases: {', '.join(PHASES)}")
    load_config(root)  # the project must have been initialised
    state = load_state(root)
    open_gates = load_workflow(root).open_gates_before(phase, state)
    if open_gates:
        names = ", ".join(f"{s.id} (/{s.skill})" for s in open_gates)
        raise StateError(
            f"Cannot approve {phase!r} yet: approve first {names}. "
            "To skip a phase, set `enabled: false` on it in .project-kit/workflow.yml."
        )
    if phase == "plan":
        load_backlog(root)
    if phase == "handoff" and not constitution_ready(root):
        raise StateError(
            f"The Spec Kit constitution is not written yet ({CONSTITUTION.as_posix()} is missing "
            "or still the template). In Claude Code run "
            f"/speckit-constitution @{INPUT_FILE.as_posix()} first."
        )
    state.approve(phase)
    if PHASES.index(phase) > PHASES.index(state.phase):
        state.phase = phase
    save_state(root, state)
    return state
