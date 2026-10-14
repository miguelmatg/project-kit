"""Thin wrapper around the GitHub CLI (``gh``), run as a subprocess (design decision D7).

``gh`` inherits the user's authentication and scopes. Transient failures (HTTP 5xx, flaky
GraphQL responses, network hiccups) are retried with exponential backoff; anything else
is raised immediately with a clear message.
"""

import json
import re
import subprocess
import time
from collections.abc import Callable, Sequence
from typing import Any

# Matched case-insensitively against stderr. Kept narrow on purpose: retrying a real
# error (bad arguments, missing permissions) would only hide it behind a delay.
_TRANSIENT = re.compile(
    r"\b(50[0-4])\b"
    r"|bad gateway|service unavailable|gateway time-?out"
    r"|something went wrong while executing your query"
    r"|timeout|timed out|connection reset|unexpected eof|\beof\b"
    r"|temporary failure|try again later|secondary rate limit",
    re.IGNORECASE,
)
_NOT_AUTHENTICATED = re.compile(
    r"gh auth login|not logged in|authentication required|bad credentials|http 401",
    re.IGNORECASE,
)

Runner = Callable[..., subprocess.CompletedProcess[str]]


class GhError(Exception):
    """A ``gh`` invocation failed."""

    def __init__(
        self,
        message: str,
        *,
        args_: Sequence[str] = (),
        returncode: int | None = None,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.gh_args = list(args_)
        self.returncode = returncode
        self.stderr = stderr


class GhNotFoundError(GhError):
    """The ``gh`` executable is not installed or not on PATH."""


class GhAuthError(GhError):
    """``gh`` is installed but there is no valid session."""


class Gh:
    """Runs ``gh`` commands. ``runner`` and ``sleep`` are injectable for tests."""

    def __init__(
        self,
        *,
        executable: str = "gh",
        retries: int = 3,
        backoff: float = 1.0,
        runner: Runner = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.executable = executable
        self.retries = retries
        self.backoff = backoff
        self._runner = runner
        self._sleep = sleep

    def run(self, *args: str, input: str | None = None) -> str:
        """Run ``gh <args>`` and return stdout. Retries transient failures."""
        cmd = [self.executable, *args]
        attempt = 0
        while True:
            try:
                proc = self._runner(
                    cmd, input=input, capture_output=True, text=True, encoding="utf-8"
                )
            except FileNotFoundError as exc:
                raise GhNotFoundError(
                    "GitHub CLI (gh) not found. Install it from https://cli.github.com/ "
                    "and make sure it is on your PATH.",
                    args_=args,
                ) from exc

            if proc.returncode == 0:
                return proc.stdout

            stderr = (proc.stderr or "").strip()
            if _NOT_AUTHENTICATED.search(stderr):
                raise GhAuthError(
                    "gh is not authenticated. Run `gh auth login` (scopes needed: repo, project).",
                    args_=args,
                    returncode=proc.returncode,
                    stderr=stderr,
                )
            if attempt < self.retries and _TRANSIENT.search(stderr):
                self._sleep(self.backoff * 2**attempt)
                attempt += 1
                continue

            shown = " ".join(args)
            raise GhError(
                f"`gh {shown}` failed (exit {proc.returncode}): {stderr or 'no error output'}",
                args_=args,
                returncode=proc.returncode,
                stderr=stderr,
            )

    def json(self, *args: str, input: str | None = None) -> Any:
        """Run ``gh <args>`` and parse stdout as JSON."""
        out = self.run(*args, input=input)
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            raise GhError(
                f"`gh {' '.join(args)}` did not return valid JSON: {exc}", args_=args
            ) from exc
