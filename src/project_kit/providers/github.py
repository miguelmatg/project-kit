"""GitHub provider: everything goes through the ``gh`` CLI (design decision D7)."""

from dataclasses import dataclass, field
from typing import Any

from project_kit.gh import Gh, GhError

_PAGE = 100


@dataclass(frozen=True)
class RepoInfo:
    full_name: str
    private: bool
    default_branch: str
    can_admin: bool


@dataclass
class Snapshot:
    """What exists in the repository right now."""

    repo: RepoInfo
    labels: set[str] = field(default_factory=set)  # lower-cased: GitHub treats them as such
    milestones: dict[str, int] = field(default_factory=dict)  # title -> number
    branches: dict[str, str] = field(default_factory=dict)  # name -> commit sha


class GitHubProvider:
    def __init__(self, gh: Gh, repo: str | None = None) -> None:
        self.gh = gh
        self._repo = repo

    # --- reading ---------------------------------------------------------------------

    def repo_info(self) -> RepoInfo:
        args = ["repo", "view"] + ([self._repo] if self._repo else [])
        data = self.gh.json(
            *args, "--json", "nameWithOwner,isPrivate,defaultBranchRef,viewerPermission"
        )
        info = RepoInfo(
            full_name=data["nameWithOwner"],
            private=bool(data["isPrivate"]),
            default_branch=(data.get("defaultBranchRef") or {}).get("name", ""),
            can_admin=data.get("viewerPermission") in ("ADMIN", "MAINTAIN"),
        )
        self._repo = info.full_name
        return info

    def _paged(self, path: str) -> list[dict[str, Any]]:
        """Collect every page of a list endpoint (``gh api --paginate`` concatenates JSON
        arrays, which cannot be parsed reliably, so pages are requested one by one)."""
        items: list[dict[str, Any]] = []
        sep = "&" if "?" in path else "?"
        page = 1
        while True:
            chunk = self.gh.json("api", f"{path}{sep}per_page={_PAGE}&page={page}")
            items.extend(chunk)
            if len(chunk) < _PAGE:
                return items
            page += 1

    def snapshot(self) -> Snapshot:
        info = self.repo_info()
        repo = info.full_name
        labels = self.gh.json("label", "list", "--repo", repo, "--limit", "1000", "--json", "name")
        return Snapshot(
            repo=info,
            labels={label["name"].lower() for label in labels},
            milestones={
                m["title"]: m["number"] for m in self._paged(f"repos/{repo}/milestones?state=all")
            },
            branches={b["name"]: b["commit"]["sha"] for b in self._paged(f"repos/{repo}/branches")},
        )

    def branch_protection_available(self) -> bool | None:
        """Probe whether this repository can have rulesets/branch protection.

        GitHub answers 403 "Upgrade to GitHub Pro or make this repository public" on
        private repositories of the free plan. ``None`` means the probe was inconclusive.
        """
        try:
            self.gh.run("api", f"repos/{self._repo}/rulesets")
        except GhError as exc:
            return False if "upgrade to github" in exc.stderr.lower() else None
        return True

    # --- writing ---------------------------------------------------------------------

    def create_label(self, name: str, color: str, description: str) -> None:
        self.gh.run(
            "label", "create", name,
            "--repo", self._repo, "--color", color, "--description", description,
        )  # fmt: skip

    def create_milestone(self, title: str, description: str) -> int:
        data = self.gh.json(
            "api", "-X", "POST", f"repos/{self._repo}/milestones",
            "-f", f"title={title}", "-f", f"description={description}",
        )  # fmt: skip
        return int(data["number"])

    def create_branch(self, name: str, sha: str) -> None:
        self.gh.run(
            "api", "-X", "POST", f"repos/{self._repo}/git/refs",
            "-f", f"ref=refs/heads/{name}", "-f", f"sha={sha}",
        )  # fmt: skip
