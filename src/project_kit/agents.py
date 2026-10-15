"""AI coding agents project-kit can hand the terminal over to after ``init``.

An agent is whatever reads the installed skills and runs ``/pk-start``. Today that is Claude
Code only; supporting another one is a new entry in ``AGENTS``.
"""

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    executable: str
    prompt: str  # what the agent is started with: the entry-point skill
    install_hint: str
    inside_env: str  # environment variable the agent sets in the shells it opens


AGENTS = (
    Agent(
        id="claude",
        name="Claude Code",
        executable="claude",
        prompt="/pk-start",
        install_hint="https://claude.com/claude-code",
        inside_env="CLAUDECODE",
    ),
)
AGENT_IDS = tuple(a.id for a in AGENTS)


def get_agent(agent_id: str) -> Agent:
    return next(a for a in AGENTS if a.id == agent_id)


def is_inside(agent: Agent, env: Mapping[str, str] | None = None) -> bool:
    """True when we run from a shell opened by this agent: launching it again would nest."""
    return bool((os.environ if env is None else env).get(agent.inside_env))


def find_executable(agent: Agent) -> str | None:
    return shutil.which(agent.executable)


def choose(
    ask: Callable[[str], str] | None = None,
    out: Callable[[str], None] = print,
) -> Agent | None:
    """Ask which agent to open now. Enter takes the first one. ``None``: the user declines."""
    out("\nOpen an AI agent now to continue with /pk-start?")
    for n, agent in enumerate(AGENTS, 1):
        out(f"  {n}) {agent.name}")
    none = len(AGENTS) + 1
    out(f"  {none}) No, I will do it myself")
    try:
        answer = (ask or input)("Choice [1]: ").strip()
    except EOFError:  # no terminal attached: never launch anything
        return None
    if answer == "":
        return AGENTS[0]
    if answer.isdigit() and 1 <= int(answer) <= len(AGENTS):
        return AGENTS[int(answer) - 1]
    return None


def launch(agent: Agent, root: Path, run: Callable[..., object] = subprocess.run) -> int:
    """Run the agent in the current terminal, in ``root``, started with its entry skill.

    Returns the agent's exit code; the terminal is inherited, so it is interactive.
    """
    exe = find_executable(agent)
    if exe is None:
        raise FileNotFoundError(agent.executable)
    result = run([exe, agent.prompt], cwd=root, check=False)
    return getattr(result, "returncode", 0)
