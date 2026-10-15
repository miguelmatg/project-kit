"""An in-memory GitHub that behaves like the real one where it matters for provisioning."""

from project_kit.approval import approve_phase
from project_kit.gh import GhError
from project_kit.providers.github import (
    ProjectItem,
    ProjectRef,
    RemoteIssue,
    RepoInfo,
    SelectField,
    SelectOption,
    Snapshot,
)


def approve_through(root, phase):
    """Approve every gated phase before ``phase``, then ``phase`` itself."""
    for earlier in ("discover", "decide", "workflow", "plan"):
        approve_phase(root, earlier)
        if earlier == phase:
            return


class FakeGitHub:
    def __init__(self, *, default_branch="main", branches=None, protection=False, fail_on=None):
        self.info = RepoInfo("o/r", True, default_branch, True)
        self.labels: set[str] = set()
        self.milestones: dict[str, int] = {}
        self.branches = {"main": "a" * 40} if branches is None else branches
        self.protection = protection
        self.fail_on = fail_on
        self.calls: list[tuple] = []

        self.issues: list[RemoteIssue] = []
        self.project: ProjectRef | None = None
        self.linked = False
        # Project fields: name -> {"id", "options": [SelectOption]}
        self.fields: dict[str, dict] = {}
        # item id -> {"number": int | None, "values": {field id: option id}}
        self.items: dict[str, dict] = {}
        self._ids = 0

    # --- helpers ---------------------------------------------------------------------

    def _id(self, prefix):
        self._ids += 1
        return f"{prefix}{self._ids}"

    def _maybe_fail(self, what):
        if self.fail_on == what:
            self.fail_on = None
            raise GhError(f"boom on {what}")

    def calls_of(self, name):
        return [c for c in self.calls if c[0] == name]

    # --- part 1 ----------------------------------------------------------------------

    def snapshot(self):
        return Snapshot(
            repo=self.info,
            labels=set(self.labels),
            milestones=dict(self.milestones),
            branches=dict(self.branches),
        )

    def branch_protection_available(self):
        return self.protection

    def create_milestone(self, title, description):
        self._maybe_fail(f"milestone:{title}")
        number = len(self.milestones) + 1
        self.milestones[title] = number
        self.calls.append(("milestone", title))
        return number

    def create_label(self, name, color, description):
        self._maybe_fail(f"label:{name}")
        self.labels.add(name.lower())
        self.calls.append(("label", name, color))

    def create_branch(self, name, sha):
        self._maybe_fail(f"branch:{name}")
        self.branches[name] = sha
        self.calls.append(("branch", name, sha))

    # --- issues ----------------------------------------------------------------------

    def add_existing_issue(self, title, body=""):
        number = len(self.issues) + 1
        issue = RemoteIssue(number, title, body, f"https://github.com/o/r/issues/{number}")
        self.issues.append(issue)
        return issue

    def list_issues(self):
        return list(self.issues)

    def create_issue(self, title, body, milestone, labels):
        self._maybe_fail(f"issue:{title}")
        assert milestone in self.milestones, "the milestone must exist before its issues"
        issue = self.add_existing_issue(title, body)
        self.calls.append(("issue", title, milestone, tuple(labels)))
        return issue

    def update_issue_body(self, number, body):
        self._maybe_fail(f"edit:{number}")
        old = self.issues[number - 1]
        self.issues[number - 1] = RemoteIssue(number, old.title, body, old.url)
        self.calls.append(("edit", number))

    # --- the Project -----------------------------------------------------------------

    def find_project(self, owner, title):
        return self.project if self.project and self.project_title == title else None

    def create_project(self, owner, title):
        self._maybe_fail("project")
        self.project = ProjectRef(1, "PVT_1", "https://github.com/users/o/projects/1")
        self.project_title = title
        self.fields = {
            "Status": {
                "id": self._id("F"),
                "options": [
                    SelectOption(n, id=self._id("O")) for n in ("Todo", "In Progress", "Done")
                ],
            }
        }
        self.calls.append(("create_project", title))
        return self.project

    def link_project(self, owner, project):
        self.linked = True
        self.calls.append(("link",))

    def project_fields(self, owner, project):
        return {
            name: SelectField(f["id"], name, {o.name: o.id for o in f["options"]})
            for name, f in self.fields.items()
        }

    def _field(self, field_id):
        return next(f for f in self.fields.values() if f["id"] == field_id)

    def field_options(self, field_id):
        return list(self._field(field_id)["options"])

    def create_select_field(self, project, name, options):
        self._maybe_fail(f"field:{name}")
        self.fields[name] = {
            "id": self._id("F"),
            "options": [
                SelectOption(o.name, o.color, o.description, self._id("O")) for o in options
            ],
        }
        self.calls.append(("create_field", name, tuple(o.name for o in options)))

    def set_select_options(self, field_id, options):
        field = self._field(field_id)
        new = [SelectOption(o.name, o.color, o.description, o.id or self._id("O")) for o in options]
        kept = {o.id for o in new}
        # Like GitHub: values pointing at an option that no longer exists are reset.
        for item in self.items.values():
            if item["values"].get(field_id) not in kept:
                item["values"].pop(field_id, None)
        field["options"] = new
        self.calls.append(("set_options", field["id"], tuple(o.name for o in new)))

    def project_items(self, owner, project):
        by_id = {f["id"]: (name, f) for name, f in self.fields.items()}
        out = []
        for item_id, item in self.items.items():
            values = {}
            for field_id, option_id in item["values"].items():
                name, field = by_id[field_id]
                option = next(o for o in field["options"] if o.id == option_id)
                values[name.lower()] = option.name
            out.append(ProjectItem(item_id, item["number"], values))
        return out

    def add_item(self, owner, project, issue_url):
        number = int(issue_url.rsplit("/", 1)[-1])
        for item_id, item in self.items.items():
            if item["number"] == number:
                return item_id
        item_id = self._id("I")
        self.items[item_id] = {"number": number, "values": {}}
        self.calls.append(("add_item", number))
        return item_id

    def set_item_values(self, project, item_id, values):
        self._maybe_fail(f"values:{item_id}")
        if values:
            self.items[item_id]["values"].update(values)
            self.calls.append(("set_values", item_id, tuple(sorted(values))))

    # --- assertions helpers ----------------------------------------------------------

    def item_values(self, number):
        for item in self.project_items("o", self.project):
            if item.number == number:
                return item.values
        return None

    def set_status(self, number, status):
        """Simulate the user moving a card."""
        item_id = next(i for i, it in self.items.items() if it["number"] == number)
        field = self.fields["Status"]
        option = next(o for o in field["options"] if o.name == status)
        self.items[item_id]["values"][field["id"]] = option.id
