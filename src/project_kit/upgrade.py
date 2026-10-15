"""``project-kit upgrade``: bring the files project-kit installed up to the current version.

``init`` never overwrites, so a project keeps the skills and templates it was created with.
``upgrade`` compares each shipped file with what is in the repository, using the digest
recorded when it was installed (see ``manifest``):

* untouched and the package has a newer one  -> **update**
* missing                                    -> **add**
* edited by you, and the package changed too -> **conflict**: yours is kept, the new one is
  written to ``.project-kit/upgrade/new/`` for you to merge
* differs and nothing was recorded           -> **unknown**: same as a conflict, unless
  ``--adopt`` says to trust the package
* recorded but no longer shipped             -> **obsolete**: reported, never deleted

Without ``--apply`` nothing is written. A file that is replaced is first copied to
``.project-kit/upgrade/backup/``.
"""

import difflib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from project_kit import __version__, installer
from project_kit.config import PROJECT_DIR, Config
from project_kit.fsutil import atomic_write_text
from project_kit.manifest import Manifest, digest, load_manifest, save_manifest

UPGRADE_DIR = Path(PROJECT_DIR) / "upgrade"
NEW_DIR = UPGRADE_DIR / "new"
BACKUP_DIR = UPGRADE_DIR / "backup"

UPDATE, ADD, CONFLICT, UNKNOWN, OBSOLETE, YOURS, OK = (
    "update",
    "add",
    "conflict",
    "unknown",
    "obsolete",
    "yours",
    "ok",
)
_SHOWN_ORDER = (UPDATE, ADD, CONFLICT, UNKNOWN, OBSOLETE)


@dataclass(frozen=True)
class Item:
    kind: str
    rel: Path
    content: bytes = b""  # the shipped version (not for obsolete files)


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list)
    previous_version: str | None = None

    def of(self, *kinds: str) -> list[Item]:
        return [i for i in self.items if i.kind in kinds]

    @property
    def changes(self) -> bool:
        return bool(self.of(UPDATE, ADD, CONFLICT, UNKNOWN, OBSOLETE))


def _classify(root: Path, rel: Path, content: bytes, manifest: Manifest) -> Item:
    dest = root / rel
    if not dest.exists():
        return Item(ADD, rel, content)
    shipped, current = digest(content), digest(dest.read_bytes())
    if current == shipped:
        return Item(OK, rel, content)
    recorded = manifest.recorded(rel)
    if recorded is None:
        return Item(UNKNOWN, rel, content)
    if current == recorded:
        return Item(UPDATE, rel, content)  # never edited; the package moved on
    if shipped == recorded:
        return Item(YOURS, rel, content)  # edited by you; nothing new to bring
    return Item(CONFLICT, rel, content)


def _obsolete(root: Path, shipped: set[Path], manifest: Manifest) -> list[Item]:
    found = {Path(p) for p in manifest.files if Path(p) not in shipped and (root / p).exists()}
    skills = root / ".claude" / "skills"
    if skills.is_dir():
        shipped_skills = {p.parts[2] for p in shipped if p.parts[:2] == (".claude", "skills")}
        for folder in skills.glob("pk-*"):
            if folder.is_dir() and folder.name not in shipped_skills:
                found.update(p.relative_to(root) for p in folder.rglob("*") if p.is_file())
    return [Item(OBSOLETE, rel) for rel in sorted(found)]


def build_plan(root: Path, config: Config) -> Plan:
    manifest = load_manifest(root)
    shipped = list(installer.shipped_files(config))
    items = [_classify(root, rel, content, manifest) for rel, content in shipped]
    items += _obsolete(root, {rel for rel, _ in shipped}, manifest)
    return Plan(items, manifest.project_kit)


def _write(root: Path, rel: Path, content: bytes) -> None:
    atomic_write_text(root / rel, content.decode("utf-8"))
    installer.make_executable(root / rel, rel)


def apply_plan(root: Path, plan: Plan, *, adopt: bool) -> list[str]:
    """Write what the plan says and update the manifest. Returns what was done, one line each."""
    manifest = load_manifest(root)
    done: list[str] = []

    for item in plan.items:
        dest = root / item.rel
        if item.kind == OK:
            manifest.record(item.rel, item.content)
        elif item.kind == ADD:
            _write(root, item.rel, item.content)
            manifest.record(item.rel, item.content)
            done.append(f"added     {item.rel.as_posix()}")
        elif item.kind in (UPDATE, UNKNOWN) and (item.kind == UPDATE or adopt):
            _write(root, BACKUP_DIR / item.rel, dest.read_bytes())
            _write(root, item.rel, item.content)
            manifest.record(item.rel, item.content)
            done.append(f"updated   {item.rel.as_posix()} (old copy in {BACKUP_DIR.as_posix()}/)")
        elif item.kind in (CONFLICT, UNKNOWN):
            _write(root, NEW_DIR / item.rel, item.content)
            done.append(f"kept      {item.rel.as_posix()} (new version in {NEW_DIR.as_posix()}/)")
    save_manifest(root, manifest, __version__)
    return done


def render_diff(root: Path, items: list[Item]) -> str:
    chunks = []
    for item in items:
        if item.kind not in (UPDATE, CONFLICT, UNKNOWN):
            continue
        current = (root / item.rel).read_text(encoding="utf-8").splitlines(keepends=True)
        shipped = item.content.decode("utf-8").splitlines(keepends=True)
        name = item.rel.as_posix()
        chunks.append(
            "".join(difflib.unified_diff(current, shipped, f"yours/{name}", f"new/{name}"))
        )
    return "\n".join(c for c in chunks if c)


_LABEL = {
    UPDATE: "update   ",
    ADD: "add      ",
    CONFLICT: "conflict ",
    UNKNOWN: "unknown  ",
    OBSOLETE: "obsolete ",
}
_WHY = {
    UPDATE: "not edited; a newer version is available",
    ADD: "new in this version, or missing here",
    CONFLICT: "you edited it and the package changed it too",
    UNKNOWN: "differs, and it is not known whether you edited it",
    OBSOLETE: "no longer shipped; delete it if you do not use it",
}


def render_plan(plan: Plan, adopt: bool) -> str:
    was = plan.previous_version or "an unknown version"
    lines = [f"project-kit {__version__}; the files were installed by {was}.", ""]
    for kind in _SHOWN_ORDER:
        for item in plan.of(kind):
            lines.append(f"  {_LABEL[kind]}{item.rel.as_posix()}")
            why = _WHY[kind]
            if kind == UNKNOWN and adopt:
                why = "differs; replaced because of --adopt"
            lines.append(f"            {why}")
    ok = len(plan.of(OK)) + len(plan.of(YOURS))
    if not plan.changes:
        lines.append("Everything is up to date.")
    lines.append(f"\n{ok} file(s) need nothing ({len(plan.of(YOURS))} edited by you).")
    return "\n".join(lines)


def run_upgrade(
    root: Path,
    config: Config,
    *,
    apply: bool,
    adopt: bool,
    show_diff: bool,
    out: Callable[[str], None] = print,
) -> int:
    plan = build_plan(root, config)
    out(render_plan(plan, adopt))
    if show_diff and (text := render_diff(root, plan.items)):
        out("\n" + text)
    pending = plan.of(UNKNOWN) and not adopt
    if not apply:
        if plan.changes:
            hint = "\nNothing was changed. Run `project-kit upgrade --apply` to apply it."
            if pending:
                hint += (
                    "\nFiles marked `unknown` come from before project-kit recorded what it "
                    "installed. If you did not edit them, add --adopt to replace them (the old "
                    f"copies are kept in {BACKUP_DIR.as_posix()}/)."
                )
            out(hint)
        return 0
    done = apply_plan(root, plan, adopt=adopt)
    out("")
    for line in done:
        out(line)
    if not done:
        out("Nothing needed writing; the record of installed files was refreshed.")
    if plan.of(CONFLICT) or (plan.of(UNKNOWN) and not adopt):
        out(
            f"\nCompare the files in {NEW_DIR.as_posix()}/ with yours, merge what you want, "
            "and delete that folder when you are done."
        )
    return 0
