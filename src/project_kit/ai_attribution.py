"""Keep AI assistants out of the commit history when the project asks for it.

Two layers, because each assistant removes itself in its own way:

* Claude Code has its own setting (``attribution`` in ``.claude/settings.json``), which stops
  it from adding the co-author trailer and the "Generated with" line.
* For any other assistant, and as a safety net, a ``commit-msg`` git hook strips co-author
  trailers that name a known AI tool. It lives in ``.githooks/`` so it is versioned and the
  whole team gets it; it is switched on with ``git config core.hooksPath .githooks``.

Both only ever add what is missing; nothing the user wrote is overwritten.
"""

import contextlib
import json
import os
from importlib.resources import files
from pathlib import Path

from project_kit.fsutil import atomic_write_text

CLAUDE_SETTINGS = Path(".claude") / "settings.json"
HOOK = Path(".githooks") / "commit-msg"
HOOKS_PATH_COMMAND = "git config core.hooksPath .githooks"


def configure_claude(root: Path) -> tuple[Path | None, str]:
    """Make Claude Code stop signing commits and PRs. Returns (changed file or None, note)."""
    path = root / CLAUDE_SETTINGS
    data: dict = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None, f"{CLAUDE_SETTINGS.as_posix()} is not valid JSON; left alone."
        if not isinstance(loaded, dict):
            return None, f"{CLAUDE_SETTINGS.as_posix()} is not a JSON object; left alone."
        data = loaded

    attribution = data.get("attribution")
    attribution = dict(attribution) if isinstance(attribution, dict) else {}
    if attribution.get("commit") == "" and attribution.get("pr") == "":
        return None, ""
    attribution["commit"] = ""
    attribution["pr"] = ""
    data["attribution"] = attribution
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return CLAUDE_SETTINGS, ""


def install_hook(root: Path) -> tuple[Path | None, str]:
    """Copy the commit-msg hook unless the project already has one. Returns (new file, note)."""
    dest = root / HOOK
    if dest.exists():
        return None, ""
    script = (files("project_kit") / "assets" / "hooks" / "commit-msg").read_text("utf-8")
    atomic_write_text(dest, script)
    with contextlib.suppress(OSError):  # no executable bit on some filesystems (Windows)
        os.chmod(dest, 0o755)
    return HOOK, ""


def hook_bytes() -> bytes:
    """The shipped commit-msg hook, as it is installed."""
    return (files("project_kit") / "assets" / "hooks" / "commit-msg").read_bytes()


def hook_is_active(root: Path) -> bool:
    """True if git is already pointed at ``.githooks`` in this repository."""
    config = root / ".git" / "config"
    if not config.is_file():
        return False
    text = config.read_text(encoding="utf-8", errors="replace")
    return any("".join(line.split()).lower() == "hookspath=.githooks" for line in text.splitlines())
