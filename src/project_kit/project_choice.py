"""Which GitHub Project does provisioning use?

Before creating anything, look for what already exists:

* the Project is already recorded in ``state.json``: use it, nothing to ask;
* ``--project`` was given: a number or the exact title of one of the owner's Projects, or a
  title for a new one;
* otherwise look at the Projects linked to the repository (plus one named like the default),
  and: none -> ask for a name and create it; one -> ask whether to use it; several -> list
  them. Without a terminal (or with ``--yes``) one is used as it is and several are an error
  that tells the caller to pass ``--project``.
"""

from collections.abc import Callable
from dataclasses import dataclass

from project_kit.config import Config
from project_kit.providers.github import GitHubProvider, ProjectRef
from project_kit.state import State

_YES = ("", "y", "yes", "s", "si", "sí")


class ProjectChoiceError(ValueError):
    """The Project to use cannot be decided without the user."""


@dataclass(frozen=True)
class Target:
    title: str
    number: int | None = None  # None: it does not exist yet and will be created
    detected: bool = False  # chosen by looking at GitHub, not remembered from an earlier run


def default_title(config: Config) -> str:
    return f"{config.project_name} Roadmap"


def stored_target(state: State, config: Config) -> Target | None:
    number = state.get_id("project", "number")
    if number is None:
        return None
    return Target(state.get_id("project", "title") or default_title(config), int(number))


def _ask_or_explain(ask: Callable[[str], str]) -> Callable[[str], str]:
    """A terminal that cannot answer (closed stdin, a tool) is an instruction, not a crash."""

    def wrapped(prompt: str) -> str:
        try:
            return ask(prompt)
        except EOFError:
            raise ProjectChoiceError(
                "There is no terminal to ask which GitHub Project to use. Choose one with "
                "--project <number or title>, or a new title to create it."
            ) from None

    return wrapped


def _describe(project: ProjectRef) -> str:
    return f"{project.title} (#{project.number}) {project.url}"


def _name_for_new(default: str, ask: Callable[[str], str]) -> Target:
    name = ask(f"Name for the new Project [{default}]: ").strip() or default
    return Target(name, None, detected=True)


def _requested(requested: str, owned: list[ProjectRef], owner: str) -> Target:
    text = requested.strip()
    if text.isdigit():
        found = next((p for p in owned if p.number == int(text)), None)
        if found is None:
            raise ProjectChoiceError(f"{owner} has no open Project number {text}.")
        return Target(found.title, found.number, detected=True)
    found = next((p for p in owned if p.title == text), None)
    if found is not None:
        return Target(found.title, found.number, detected=True)
    return Target(text, None, detected=True)


def resolve_target(
    provider: GitHubProvider,
    owner: str,
    config: Config,
    state: State,
    *,
    requested: str | None,
    interactive: bool,
    assume_yes: bool,
    ask: Callable[[str], str] | None = None,
    out: Callable[[str], None] = print,
) -> Target:
    stored = stored_target(state, config)
    if stored and not requested:
        return stored

    owned = provider.list_projects(owner)
    if requested:
        return _requested(requested, owned, owner)

    default = default_title(config)
    candidates = list(provider.linked_projects())
    linked = {p.number for p in candidates}
    candidates += [p for p in owned if p.title == default and p.number not in linked]
    can_ask = interactive and not assume_yes
    ask = _ask_or_explain(ask or input)

    if not candidates:
        if can_ask:
            out("No Project is linked to this repository yet.")
            return _name_for_new(default, ask)
        return Target(default, None, detected=True)

    if len(candidates) == 1:
        only = candidates[0]
        if not can_ask:
            return Target(only.title, only.number, detected=True)
        answer = ask(f"Use the existing Project {_describe(only)}? [Y/n] ").strip().lower()
        if answer in _YES:
            return Target(only.title, only.number, detected=True)
        return _name_for_new(default, ask)

    listing = [f"  {n}) {_describe(p)}" for n, p in enumerate(candidates, 1)]
    if not can_ask:
        raise ProjectChoiceError(
            "Several Projects match this repository:\n"
            + "\n".join(listing)
            + "\nChoose one with --project <number or title>, or a new title to create one."
        )
    out("Several Projects are linked to this repository:")
    for line in listing:
        out(line)
    out(f"  {len(candidates) + 1}) Create a new one")
    answer = ask("Choice [1]: ").strip() or "1"
    if not answer.isdigit() or not 1 <= int(answer) <= len(candidates) + 1:
        raise ProjectChoiceError(f"{answer!r} is not one of the options.")
    if int(answer) == len(candidates) + 1:
        return _name_for_new(default, ask)
    chosen = candidates[int(answer) - 1]
    return Target(chosen.title, chosen.number, detected=True)
