"""GitHub provider: everything goes through the ``gh`` CLI (design decision D7)."""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from project_kit.gh import Gh, GhError

_PAGE = 100
_ISSUE_MARKER = re.compile(r"<!--\s*project-kit:id=([a-z0-9]+(?:-[a-z0-9]+)*)\s*-->")


@dataclass(frozen=True)
class RepoInfo:
    full_name: str
    private: bool
    default_branch: str
    can_admin: bool

    @property
    def owner(self) -> str:
        return self.full_name.split("/")[0]


@dataclass
class Snapshot:
    """What exists in the repository right now."""

    repo: RepoInfo
    labels: set[str] = field(default_factory=set)  # lower-cased: GitHub treats them as such
    milestones: dict[str, int] = field(default_factory=dict)  # title -> number
    branches: dict[str, str] = field(default_factory=dict)  # name -> commit sha


@dataclass(frozen=True)
class ProjectRef:
    number: int
    id: str
    url: str
    title: str = ""


@dataclass
class SelectField:
    """A single-select Project field. ``options`` maps option name -> option id."""

    id: str
    name: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SelectOption:
    name: str
    color: str = "GRAY"
    description: str = ""
    id: str | None = None  # present for options that already exist, so they are kept


@dataclass
class ProjectItem:
    id: str
    number: int | None  # None for draft items
    values: dict[str, str] = field(default_factory=dict)  # lower-cased field name -> option


@dataclass(frozen=True)
class RemoteIssue:
    number: int
    title: str
    body: str
    url: str

    @property
    def local_id(self) -> str | None:
        match = _ISSUE_MARKER.search(self.body or "")
        return match.group(1) if match else None


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

    # --- writing: labels, milestones, branches ---------------------------------------

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

    # --- issues ----------------------------------------------------------------------

    def list_issues(self) -> list[RemoteIssue]:
        rows = self.gh.json(
            "issue", "list", "--repo", self._repo, "--state", "all", "--limit", "1000",
            "--json", "number,title,body,url",
        )  # fmt: skip
        return [RemoteIssue(r["number"], r["title"], r.get("body") or "", r["url"]) for r in rows]

    def create_issue(self, title: str, body: str, milestone: str, labels: list[str]) -> RemoteIssue:
        args = ["issue", "create", "--repo", self._repo, "--title", title, "--body-file", "-"]
        args += ["--milestone", milestone]
        for label in labels:
            args += ["--label", label]
        url = self.gh.run(*args, input=body).strip().splitlines()[-1]
        return RemoteIssue(int(url.rstrip("/").rsplit("/", 1)[-1]), title, body, url)

    def update_issue_body(self, number: int, body: str) -> None:
        self.gh.run(
            "issue", "edit", str(number), "--repo", self._repo, "--body-file", "-", input=body
        )

    # --- the Project -----------------------------------------------------------------

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        data = self.gh.json(
            "api", "graphql", "--input", "-",
            input=json.dumps({"query": query, "variables": variables}),
        )  # fmt: skip
        if data.get("errors"):
            raise GhError(f"GraphQL error: {data['errors'][0].get('message', data['errors'])}")
        return data["data"]

    def list_projects(self, owner: str) -> list[ProjectRef]:
        """The owner's open Projects."""
        data = self.gh.json(
            "project", "list", "--owner", owner, "--limit", "200", "--format", "json"
        )
        return [
            ProjectRef(p["number"], p["id"], p["url"], p["title"])
            for p in data["projects"]
            if not p.get("closed")
        ]

    def linked_projects(self) -> list[ProjectRef]:
        """The open Projects already linked to this repository."""
        owner, _, name = self._repo.partition("/")
        data = self._graphql(
            "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) {"
            " projectsV2(first: 50) { nodes { number id url title closed } } } }",
            {"owner": owner, "name": name},
        )
        nodes = (data.get("repository") or {}).get("projectsV2", {}).get("nodes") or []
        return [
            ProjectRef(n["number"], n["id"], n["url"], n["title"])
            for n in nodes
            if n and not n.get("closed")
        ]

    def find_project(self, owner: str, title: str, number: int | None = None) -> ProjectRef | None:
        """By number when given (a Project chosen earlier), else by exact title."""
        for p in self.list_projects(owner):
            if p.number == number if number is not None else p.title == title:
                return p
        return None

    def create_project(self, owner: str, title: str) -> ProjectRef:
        p = self.gh.json(
            "project", "create", "--owner", owner, "--title", title, "--format", "json"
        )
        return ProjectRef(p["number"], p["id"], p["url"])

    def link_project(self, owner: str, project: ProjectRef) -> None:
        """Link the Project to the repository (repeating it is harmless)."""
        self.gh.run("project", "link", str(project.number), "--owner", owner, "--repo", self._repo)

    def project_fields(self, owner: str, project: ProjectRef) -> dict[str, SelectField]:
        data = self.gh.json(
            "project", "field-list", str(project.number),
            "--owner", owner, "--limit", "100", "--format", "json",
        )  # fmt: skip
        return {
            f["name"]: SelectField(f["id"], f["name"], {o["name"]: o["id"] for o in f["options"]})
            for f in data["fields"]
            if "options" in f
        }

    def field_options(self, field_id: str) -> list[SelectOption]:
        """Options with their colour and description, which ``field-list`` does not return."""
        data = self._graphql(
            "query($id:ID!){node(id:$id){... on ProjectV2SingleSelectField"
            "{options{id name color description}}}}",
            {"id": field_id},
        )
        return [
            SelectOption(o["name"], o["color"], o["description"] or "", o["id"])
            for o in data["node"]["options"]
        ]

    @staticmethod
    def _option_input(options: list[SelectOption]) -> list[dict[str, str]]:
        rows = []
        for o in options:
            row = {"name": o.name, "color": o.color, "description": o.description}
            if o.id:
                row["id"] = o.id
            rows.append(row)
        return rows

    def create_select_field(
        self, project: ProjectRef, name: str, options: list[SelectOption]
    ) -> None:
        self._graphql(
            "mutation($p:ID!,$n:String!,$o:[ProjectV2SingleSelectFieldOptionInput!]){"
            "createProjectV2Field(input:{projectId:$p,dataType:SINGLE_SELECT,name:$n,"
            "singleSelectOptions:$o}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}",
            {"p": project.id, "n": name, "o": self._option_input(options)},
        )

    def set_select_options(self, field_id: str, options: list[SelectOption]) -> None:
        """Replace a field's options. Options passed with an ``id`` keep their identity."""
        self._graphql(
            "mutation($f:ID!,$o:[ProjectV2SingleSelectFieldOptionInput!]!){"
            "updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:$o})"
            "{projectV2Field{... on ProjectV2SingleSelectField{id}}}}",
            {"f": field_id, "o": self._option_input(options)},
        )

    def project_items(self, owner: str, project: ProjectRef) -> list[ProjectItem]:
        data = self.gh.json(
            "project", "item-list", str(project.number),
            "--owner", owner, "--limit", "2000", "--format", "json",
        )  # fmt: skip
        fields = ("status", "phase", "kind", "priority", "size")
        return [
            ProjectItem(
                id=i["id"],
                number=(i.get("content") or {}).get("number"),
                values={k: i[k] for k in fields if i.get(k)},
            )
            for i in data["items"]
        ]

    def add_item(self, owner: str, project: ProjectRef, issue_url: str) -> str:
        """Add an issue to the Project; if it is already there this returns the same item."""
        data = self.gh.json(
            "project", "item-add", str(project.number),
            "--owner", owner, "--url", issue_url, "--format", "json",
        )  # fmt: skip
        return data["id"]

    def set_item_values(self, project: ProjectRef, item_id: str, values: dict[str, str]) -> None:
        """Set several single-select fields of one item in a single request.

        ``values`` maps field id -> option id.
        """
        if not values:
            return
        params = ["$p:ID!", "$i:ID!"]
        calls = []
        variables: dict[str, Any] = {"p": project.id, "i": item_id}
        for n, (field_id, option_id) in enumerate(values.items()):
            params += [f"$f{n}:ID!", f"$o{n}:String!"]
            variables |= {f"f{n}": field_id, f"o{n}": option_id}
            calls.append(
                f"a{n}:updateProjectV2ItemFieldValue(input:{{projectId:$p,itemId:$i,"
                f"fieldId:$f{n},value:{{singleSelectOptionId:$o{n}}}}}){{projectV2Item{{id}}}}"
            )
        self._graphql(f"mutation({','.join(params)}){{{' '.join(calls)}}}", variables)
