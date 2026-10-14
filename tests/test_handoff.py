import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from project_kit import handoff, installer
from project_kit.approval import approve_phase
from project_kit.backlog import backlog_path
from project_kit.cli import main
from project_kit.config import Config, ConfigError
from project_kit.handoff import (
    INPUT_FILE,
    MANAGED_HEADER,
    SpecKit,
    build_constitution_input,
    detect_speckit,
    install_steps,
    is_tested,
    list_decisions,
    run_handoff,
    write_managed,
)
from project_kit.templating import TemplateError, render


@pytest.fixture
def project(tmp_path):
    installer.init_project(
        tmp_path,
        Config(
            project_name="Acme",
            language="es",
            branches={"main": "trunk", "release": "stage", "develop": "dev"},
        ),
    )
    return tmp_path


class FakeSystem:
    """Stands in for PATH lookups and for running ``uv``/``specify``."""

    def __init__(self, root, *, tools=(), version="1.2.0", fail_on=None):
        self.root = root
        self.tools = {t: f"/bin/{t}" for t in tools}
        self.version = version
        self.fail_on = fail_on
        self.ran: list[list[str]] = []

    def which(self, name):
        return self.tools.get(name)

    def __call__(self, cmd, **kwargs):
        if cmd[1:] == ["--version"]:
            return subprocess.CompletedProcess(cmd, 0, f"specify {self.version}\n", "")
        if cmd[:3] == ["uv", "tool", "dir"]:
            return subprocess.CompletedProcess(cmd, 0, "/nowhere\n", "")
        self.ran.append(cmd)
        if self.fail_on and self.fail_on in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 1)
        if cmd[:3] == ["uv", "tool", "install"]:
            self.tools["specify"] = "/bin/specify"
        if "init" in cmd:
            spec = self.root / ".specify"
            spec.mkdir(exist_ok=True)
            (spec / "init-options.json").write_text(
                json.dumps({"speckit_version": self.version}), encoding="utf-8"
            )
        return subprocess.CompletedProcess(cmd, 0)


def make_specify_dir(root, version="1.2.0"):
    spec = root / ".specify"
    (spec / "memory").mkdir(parents=True)
    (spec / "memory" / "constitution.md").write_text("owned by spec kit", encoding="utf-8")
    (spec / "init-options.json").write_text(
        json.dumps({"speckit_version": version}), encoding="utf-8"
    )


def tree_hash(path: Path) -> dict[str, str]:
    return {
        str(p.relative_to(path)): hashlib.sha1(p.read_bytes()).hexdigest()
        for p in sorted(path.rglob("*"))
        if p.is_file()
    }


def run(project, system, *, install=False, yes=False, dry_run=False, answer=True):
    out, asked = [], []

    def confirm(question):
        asked.append(question)
        return answer

    code = run_handoff(
        project,
        install=install,
        assume_yes=yes,
        dry_run=dry_run,
        confirm=confirm,
        out=out.append,
        which=system.which,
        runner=system,
    )
    return code, "\n".join(out), asked


# --- templating ----------------------------------------------------------------------------


def test_render_substitutes_variables_with_optional_spaces():
    assert render("a {{x}} b {{ y.z }}", {"x": "1", "y.z": "2"}) == "a 1 b 2"


def test_render_rejects_unknown_variables_listing_them():
    with pytest.raises(TemplateError, match="nada, nope"):
        render("{{nope}} {{ok}} {{nada}}", {"ok": "1"})


# --- the constitution input ----------------------------------------------------------------


def test_input_uses_project_settings_and_has_no_unreplaced_variables(project):
    text = build_constitution_input(project, Config(project_name="Acme", language="es",
        branches={"main": "trunk", "release": "stage", "develop": "dev"}))  # fmt: skip
    assert text.startswith(MANAGED_HEADER)
    assert "# Acme constitution input" in text
    assert "`trunk` (released product), `stage`" in text and "from `dev`" in text
    assert "written in `es`" in text
    assert "{{" not in text and "}}" not in text


def test_input_is_deterministic(project):
    config = Config(project_name="Acme")
    assert build_constitution_input(project, config) == build_constitution_input(project, config)


def test_input_is_governance_only():
    """Spec Kit refuses non-governance content, so the template must not ask for building."""
    template = (Path(handoff.__file__).parent / "assets/templates/constitution-input.md").read_text(
        encoding="utf-8"
    )
    assert "nothing in this document asks for features to be built" in template


def test_without_adrs_the_stack_is_pending(project):
    text = build_constitution_input(project, Config(project_name="Acme"))
    assert "not decided yet" in text and "No decisions are recorded yet." in text


def test_adrs_are_listed_with_title_and_status(project):
    adr = project / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "0002-db.md").write_text("# Use PostgreSQL\n\nStatus: Accepted\n", encoding="utf-8")
    (adr / "0001-lang.md").write_text("# Use Python\n\n**Status:** Proposed\n", encoding="utf-8")
    (adr / "0003-nostatus.md").write_text("# Plain\n", encoding="utf-8")
    assert list_decisions(project) == [
        "- `docs/adr/0001-lang.md`: Use Python (Proposed)",
        "- `docs/adr/0002-db.md`: Use PostgreSQL (Accepted)",
        "- `docs/adr/0003-nostatus.md`: Plain",
    ]
    text = build_constitution_input(project, Config(project_name="Acme"))
    assert "defined by the decisions on record below" in text
    assert "Use PostgreSQL (Accepted)" in text


def test_references_mention_existing_documents_and_backlog_phases(project):
    (project / "docs/project").mkdir(parents=True)
    (project / "docs/project/brief.md").write_text("# Brief", encoding="utf-8")
    backlog_path(project).write_text(
        json.dumps({"version": 1, "phases": [{"id": "a", "title": "v0.1"}], "issues": []}),
        encoding="utf-8",
    )
    text = build_constitution_input(project, Config(project_name="Acme"))
    assert "- Project documents: `docs/project/brief.md`." in text
    assert "- Delivery phases: v0.1." in text


def test_project_specific_rules_are_appended_from_the_extra_file(project):
    (project / ".project-kit/handoff").mkdir(parents=True, exist_ok=True)
    (project / handoff.EXTRA_FILE).write_text("- Never store card numbers.\n", encoding="utf-8")
    text = build_constitution_input(project, Config(project_name="Acme"))
    assert "## Project-specific rules\n\n- Never store card numbers." in text
    assert text.index("Project-specific rules") < text.index("## Governance")


def test_a_project_template_overrides_the_shipped_one(project):
    (project / ".project-kit/templates/constitution-input.md").write_text(
        "mine: {{project_name}} on {{branches.develop}}", encoding="utf-8"
    )
    assert build_constitution_input(project, Config(project_name="Acme")) == "mine: Acme on develop"


def test_an_override_with_a_typo_is_reported(project):
    (project / ".project-kit/templates/constitution-input.md").write_text(
        "{{project_nmae}}", encoding="utf-8"
    )
    with pytest.raises(TemplateError, match="project_nmae"):
        build_constitution_input(project, Config(project_name="Acme"))


def test_init_installs_the_template_so_it_can_be_overridden(project):
    assert (project / ".project-kit/templates/constitution-input.md").is_file()


# --- writing managed files -----------------------------------------------------------------


def test_write_managed_lifecycle(tmp_path):
    path = tmp_path / "x" / "f.md"
    assert write_managed(path, f"{MANAGED_HEADER}\none") == "created"
    assert write_managed(path, f"{MANAGED_HEADER}\none") == "unchanged"
    assert write_managed(path, f"{MANAGED_HEADER}\ntwo") == "updated"
    assert path.read_text(encoding="utf-8").endswith("two")


def test_a_file_without_the_header_is_never_overwritten(tmp_path):
    path = tmp_path / "f.md"
    path.write_text("my own words", encoding="utf-8")
    assert write_managed(path, f"{MANAGED_HEADER}\ngenerated") == "kept"
    assert path.read_text(encoding="utf-8") == "my own words"


# --- detecting Spec Kit --------------------------------------------------------------------


def test_detect_reads_cli_and_project_versions(project):
    make_specify_dir(project, "1.1.0")
    sk = detect_speckit(project, FakeSystem(project, tools=["specify"]).which, FakeSystem(project))
    assert sk == SpecKit("/bin/specify", "1.2.0", True, "1.1.0")


def test_detect_when_nothing_is_there(project):
    sk = detect_speckit(project, FakeSystem(project).which, FakeSystem(project))
    assert sk == SpecKit(None, None, False, None) and not sk.installed


@pytest.mark.parametrize(
    ("version", "tested"),
    [
        ("1.2.0", True),
        ("1.2.7", True),
        ("1.2", True),
        ("1.3.0", False),
        ("1.20.0", False),
        (None, False),
    ],
)
def test_is_tested(version, tested):
    assert is_tested(version) is tested


# --- install steps -------------------------------------------------------------------------


def test_nothing_to_install_when_spec_kit_is_ready():
    steps, problems = install_steps(SpecKit("/bin/specify", "1.2.0", True, "1.2.0"), lambda n: None)
    assert steps == [] and problems == []


def test_missing_everything_installs_then_initialises():
    steps, problems = install_steps(SpecKit(None, None, False, None), lambda n: "/bin/uv")
    assert [s.command[:3] for s in steps] == [
        ["uv", "tool", "install"],
        ["specify", "init", "--here"],
    ]
    assert steps[0].command == ["uv", "tool", "install", "specify-cli"]
    assert "--integration" in steps[1].command and "claude" in steps[1].command
    assert problems == []


def test_missing_uv_blocks_the_installation():
    steps, problems = install_steps(SpecKit(None, None, False, None), lambda n: None)
    assert "uv is needed" in problems[0]


def test_cli_present_but_repo_not_initialised_only_initialises():
    steps, _ = install_steps(SpecKit("/bin/specify", "1.2.0", False, None), lambda n: None)
    assert [s.command[1] for s in steps] == ["init"]


# --- running -------------------------------------------------------------------------------


def test_with_spec_kit_ready_it_writes_the_input_and_never_touches_specify(project):
    make_specify_dir(project)
    before = tree_hash(project / ".specify")
    system = FakeSystem(project, tools=["specify"])

    code, out, asked = run(project, system)

    assert code == 0 and asked == [] and system.ran == []
    assert (project / INPUT_FILE).read_text(encoding="utf-8").startswith(MANAGED_HEADER)
    assert "constitution-input.md: created." in out
    assert "/speckit-constitution @.project-kit/handoff/constitution-input.md" in out
    assert "project-kit approve handoff" in out
    assert tree_hash(project / ".specify") == before


def test_running_it_twice_changes_nothing(project):
    make_specify_dir(project)
    system = FakeSystem(project, tools=["specify"])
    run(project, system)
    first = (project / INPUT_FILE).read_bytes()
    _, out, _ = run(project, system)
    assert "unchanged" in out and (project / INPUT_FILE).read_bytes() == first


def test_dry_run_writes_nothing_and_runs_nothing(project):
    system = FakeSystem(project, tools=["uv"])
    code, out, _ = run(project, system, install=True, dry_run=True)
    assert code == 0 and "Dry run" in out and "# Acme constitution input" in out
    assert not (project / INPUT_FILE).exists() and system.ran == []


def test_without_the_flag_it_only_suggests_installing_spec_kit(project):
    system = FakeSystem(project, tools=["uv"])
    code, out, asked = run(project, system)
    assert code == 0 and "--install-speckit" in out and asked == [] and system.ran == []
    assert "Next steps" not in out and (project / INPUT_FILE).exists()


def test_installing_asks_first_and_a_no_runs_nothing(project):
    system = FakeSystem(project, tools=["uv"])
    code, out, asked = run(project, system, install=True, answer=False)
    assert code == 1 and "Aborted" in out and system.ran == [] and len(asked) == 1
    assert "uv tool install specify-cli" in out and "merges its files" in out


def test_installing_runs_both_steps_then_shows_the_next_steps(project):
    system = FakeSystem(project, tools=["uv"])
    code, out, _ = run(project, system, install=True, yes=True)
    assert code == 0
    assert system.ran[0] == ["uv", "tool", "install", "specify-cli"]
    assert system.ran[1][:3] == ["/bin/specify", "init", "--here"]  # the resolved executable
    assert (project / ".specify").is_dir() and "Next steps" in out


def test_a_failed_step_stops_everything(project):
    system = FakeSystem(project, tools=["uv"], fail_on="tool install")
    code, out, _ = run(project, system, install=True, yes=True)
    assert code == 1 and "Stopped" in out and len(system.ran) == 1
    assert not (project / ".specify").exists()


def test_missing_uv_is_reported_as_blocking(project):
    code, out, _ = run(project, FakeSystem(project), install=True, yes=True)
    assert code == 1 and "BLOCKING" in out and "uv is needed" in out


def test_an_untested_version_only_warns(project):
    make_specify_dir(project, "9.9.0")
    code, out, _ = run(project, FakeSystem(project, tools=["specify"], version="9.9.0"))
    assert code == 0 and "version 9.9.0" in out and "1.2.x" in out


def test_a_taken_over_input_file_is_left_alone(project):
    make_specify_dir(project)
    (project / INPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    (project / INPUT_FILE).write_text("hand written", encoding="utf-8")
    _, out, _ = run(project, FakeSystem(project, tools=["specify"]))
    assert (project / INPUT_FILE).read_text(encoding="utf-8") == "hand written"
    assert "no longer has the project-kit:managed header" in out


def test_an_unapproved_plan_is_only_a_note(project):
    make_specify_dir(project)
    _, out, _ = run(project, FakeSystem(project, tools=["specify"]))
    assert "plan has not been approved" in out
    backlog_path(project).write_text(
        json.dumps({"version": 1, "phases": [], "issues": []}), encoding="utf-8"
    )
    approve_phase(project, "plan")
    _, out, _ = run(project, FakeSystem(project, tools=["specify"]))
    assert "plan has not been approved" not in out


def test_it_needs_an_initialised_project(tmp_path):
    with pytest.raises(ConfigError):
        run(tmp_path, FakeSystem(tmp_path))


def test_cli_reports_a_missing_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["handoff", "--dry-run"]) == 1
    assert "project-kit init" in capsys.readouterr().err
