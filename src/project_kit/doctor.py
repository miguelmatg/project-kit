"""``project-kit doctor``: check that the tools project-kit relies on are available."""

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from project_kit.gh import Gh, GhAuthError, GhError, GhNotFoundError

REQUIRED_GH_SCOPES = ("repo", "project")


class Status(Enum):
    OK = "ok"
    WARN = "warn"  # something optional is missing; project-kit still works
    FAIL = "fail"  # a hard requirement is missing; project-kit cannot do its job


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str
    hint: str = ""


Which = Callable[[str], str | None]
Runner = Callable[..., subprocess.CompletedProcess[str]]


def _version(exe: str, runner: Runner) -> str:
    """First line of ``<exe> --version``, or an empty string if it cannot be read."""
    try:
        proc = runner([exe, "--version"], capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return ""
    return (proc.stdout or "").strip().splitlines()[0] if proc.returncode == 0 else ""


def check_git(which: Which, runner: Runner) -> Check:
    if not which("git"):
        return Check(
            "git",
            Status.FAIL,
            "not found",
            "Install Git from https://git-scm.com/downloads and make sure it is on PATH.",
        )
    return Check("git", Status.OK, _version("git", runner) or "found")


def parse_scopes(auth_status: str) -> list[str] | None:
    """Scopes listed by ``gh auth status``; ``None`` if the output does not list any."""
    match = re.search(r"token scopes:\s*(.+)", auth_status, re.IGNORECASE)
    if not match:
        return None
    return re.findall(r"[\w:.-]+", match.group(1))


def check_gh(gh: Gh) -> list[Check]:
    """One check for the CLI itself and, if usable, one for the session and its scopes."""
    try:
        version = gh.run("--version").strip().splitlines()[0]
    except GhNotFoundError:
        return [
            Check(
                "gh",
                Status.FAIL,
                "not found",
                "Install the GitHub CLI from https://cli.github.com/ and make sure it is on PATH.",
            )
        ]
    except GhError as exc:
        return [Check("gh", Status.FAIL, str(exc))]

    checks = [Check("gh", Status.OK, version)]
    try:
        scopes = parse_scopes(gh.run("auth", "status"))
    except GhAuthError:
        checks.append(
            Check(
                "gh auth",
                Status.FAIL,
                "not logged in",
                "Run `gh auth login` and grant the scopes: " + ", ".join(REQUIRED_GH_SCOPES),
            )
        )
        return checks
    except GhError as exc:
        checks.append(Check("gh auth", Status.FAIL, str(exc)))
        return checks

    if scopes is None:
        # Fine-grained tokens and GH_TOKEN do not list scopes, so this cannot be verified.
        checks.append(
            Check(
                "gh auth",
                Status.WARN,
                "logged in, but token scopes cannot be verified",
                f"Make sure the token allows: {', '.join(REQUIRED_GH_SCOPES)}.",
            )
        )
        return checks

    missing = [s for s in REQUIRED_GH_SCOPES if s not in scopes]
    if missing:
        checks.append(
            Check(
                "gh auth",
                Status.FAIL,
                f"missing scopes: {', '.join(missing)}",
                f"Run `gh auth refresh -s {','.join(missing)}`.",
            )
        )
    else:
        checks.append(Check("gh auth", Status.OK, f"scopes: {', '.join(scopes)}"))
    return checks


def check_uv(which: Which, runner: Runner) -> Check:
    if not which("uv"):
        return Check(
            "uv",
            Status.WARN,
            "not found",
            "Needed to install Spec Kit. See https://docs.astral.sh/uv/ .",
        )
    return Check("uv", Status.OK, _version("uv", runner) or "found")


def check_speckit(which: Which, runner: Runner, cwd: Path) -> Check:
    initialised = (cwd / ".specify").is_dir()
    if which("specify"):
        version = _version("specify", runner)
        detail = version or "specify found"
        return Check(
            "spec-kit", Status.OK, detail + ("" if initialised else " (not initialised here)")
        )
    if initialised:
        return Check("spec-kit", Status.OK, ".specify/ found (specify CLI not on PATH)")
    return Check(
        "spec-kit",
        Status.WARN,
        "not installed",
        "Optional until the handoff phase; project-kit can install it for you.",
    )


def run_checks(
    *,
    gh: Gh | None = None,
    which: Which = shutil.which,
    runner: Runner = subprocess.run,
    cwd: Path | None = None,
) -> list[Check]:
    return [
        check_git(which, runner),
        *check_gh(gh or Gh()),
        check_uv(which, runner),
        check_speckit(which, runner, cwd or Path.cwd()),
    ]


_MARK = {Status.OK: "ok  ", Status.WARN: "warn", Status.FAIL: "FAIL"}


def render(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        lines.append(f"[{_MARK[c.status]}] {c.name}: {c.detail}")
        if c.hint and c.status is not Status.OK:
            lines.append(f"       -> {c.hint}")
    failed = sum(c.status is Status.FAIL for c in checks)
    warned = sum(c.status is Status.WARN for c in checks)
    if failed:
        lines.append(f"\n{failed} blocking problem(s). Fix them before using project-kit.")
    elif warned:
        lines.append(f"\nReady, with {warned} warning(s).")
    else:
        lines.append("\nAll good.")
    return "\n".join(lines)


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.status is Status.FAIL for c in checks) else 0
