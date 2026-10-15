"""``project-kit init``: install project-kit's files into a target repository.

Rule: never overwrite. A file that already exists is kept as it is (whether or not it
differs from the shipped one), so manual edits are safe and running ``init`` again is a
no-op. Updating shipped files is the job of ``upgrade``; to make that possible ``init`` records
in ``.project-kit/installed.json`` the digest of every shipped file it finds identical to ours.
"""

import contextlib
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from project_kit import __version__, ai_attribution
from project_kit.config import PROJECT_DIR, Config, config_path, load_config, save_config
from project_kit.fsutil import atomic_write_text
from project_kit.manifest import digest, load_manifest, save_manifest
from project_kit.state import State, save_state, state_path

# Where each shipped asset directory lands in the target repository.
_ASSET_TARGETS = {
    "skills": Path(".claude") / "skills",
    "templates": Path(PROJECT_DIR) / "templates",
    "project": Path(PROJECT_DIR),
}


@dataclass
class Report:
    created: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)  # exists and identical to ours
    kept: list[Path] = field(default_factory=list)  # exists and differs: left alone
    notes: list[str] = field(default_factory=list)  # things the user should know or do


def _walk(node: Traversable, prefix: Path = Path()) -> Iterator[tuple[Path, Traversable]]:
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        rel = prefix / child.name
        if child.is_dir():
            yield from _walk(child, rel)
        elif child.name != "__pycache__":
            yield rel, child


def iter_assets() -> Iterator[tuple[Path, bytes]]:
    """Every shipped file as (path relative to the target repo, content)."""
    assets = files("project_kit") / "assets"
    for kind, target in _ASSET_TARGETS.items():
        for rel, node in _walk(assets / kind):
            yield target / rel, node.read_bytes()


def shipped_files(config: Config) -> Iterator[tuple[Path, bytes]]:
    """Everything project-kit installs for this project, as ``init`` and ``upgrade`` see it."""
    yield from iter_assets()
    if not config.ai_coauthor:  # the commit-msg hook only exists when the project asked for it
        yield ai_attribution.HOOK, ai_attribution.hook_bytes()


def make_executable(path: Path, rel: Path) -> None:
    if rel.name == ai_attribution.HOOK.name:
        with contextlib.suppress(OSError):  # no executable bit on some filesystems (Windows)
            os.chmod(path, 0o755)


def _install_file(root: Path, rel: Path, content: bytes, report: Report) -> None:
    dest = root / rel
    if dest.exists():
        same = digest(dest.read_bytes()) == digest(content)
        (report.unchanged if same else report.kept).append(rel)
        return
    atomic_write_text(dest, content.decode("utf-8"))
    report.created.append(rel)


def _apply_ai_policy(root: Path, config: Config, report: Report) -> None:
    """If the project asks that AI assistants are not co-authors, set that up (idempotent)."""
    if config.ai_coauthor:
        return
    for create in (ai_attribution.configure_claude, ai_attribution.install_hook):
        changed, note = create(root)
        if changed:
            report.created.append(changed)
        if note:
            report.notes.append(note)
    if not ai_attribution.hook_is_active(root):
        report.notes.append(
            "To strip AI co-author trailers from every commit, run: "
            + ai_attribution.HOOKS_PATH_COMMAND
        )


def init_project(root: Path, config: Config) -> Report:
    """Install project-kit into ``root``. ``config`` is used only if there is none yet."""
    report = Report()

    cfg = config_path(root)
    if cfg.exists():
        load_config(root)  # fail early, with a clear message, if the existing one is invalid
        report.unchanged.append(cfg.relative_to(root))
    else:
        save_config(root, config)
        report.created.append(cfg.relative_to(root))

    st = state_path(root)
    if st.exists():
        report.unchanged.append(st.relative_to(root))
    else:
        save_state(root, State())
        report.created.append(st.relative_to(root))

    for rel, content in iter_assets():
        _install_file(root, rel, content, report)
    config = load_config(root)
    _apply_ai_policy(root, config, report)
    _record_installed(root, config)
    return report


def _record_installed(root: Path, config: Config) -> None:
    """Remember the digest of each shipped file that is, as of now, exactly ours.

    A file that differs is not recorded: nobody knows whether it is an old version of ours or
    an edit, and ``upgrade`` must not guess that for itself.
    """
    manifest = load_manifest(root)
    for rel, content in shipped_files(config):
        path = root / rel
        if path.exists() and digest(path.read_bytes()) == digest(content):
            manifest.record(rel, content)
    save_manifest(root, manifest, __version__)
