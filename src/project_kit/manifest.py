""".project-kit/installed.json: what ``init`` and ``upgrade`` put in the repository.

For every shipped file it keeps the digest of the version that was installed. That is what lets
``upgrade`` tell "you never touched it, the package has a newer one" apart from "you edited it":
a file whose digest still matches the record is untouched.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from project_kit.config import PROJECT_DIR
from project_kit.fsutil import atomic_write_text

MANIFEST_VERSION = 1


def manifest_path(root: Path) -> Path:
    return root / PROJECT_DIR / "installed.json"


def digest(data: bytes) -> str:
    """SHA-256 of the content with line endings normalised, so a checkout with CRLF (git's
    autocrlf on Windows) is not mistaken for an edit."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


@dataclass
class Manifest:
    project_kit: str | None = None  # version that last wrote the files
    files: dict[str, str] = field(default_factory=dict)  # posix path -> digest as installed

    def record(self, rel: Path, content: bytes) -> None:
        self.files[rel.as_posix()] = digest(content)

    def recorded(self, rel: Path) -> str | None:
        return self.files.get(rel.as_posix())


def load_manifest(root: Path) -> Manifest:
    """The manifest, or an empty one for a project that predates it or has a damaged file."""
    try:
        data = json.loads(manifest_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Manifest()
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        return Manifest()
    files = data.get("files")
    if not isinstance(files, dict):
        return Manifest()
    clean = {k: v for k, v in files.items() if isinstance(k, str) and isinstance(v, str)}
    version = data.get("project_kit")
    return Manifest(version if isinstance(version, str) else None, clean)


def save_manifest(root: Path, manifest: Manifest, version: str) -> None:
    manifest.project_kit = version
    body = {
        "version": MANIFEST_VERSION,
        "project_kit": version,
        "files": dict(sorted(manifest.files.items())),
    }
    atomic_write_text(manifest_path(root), json.dumps(body, indent=2) + "\n")
