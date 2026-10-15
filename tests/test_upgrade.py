import json
from pathlib import Path

import pytest

from project_kit import ai_attribution, installer, upgrade
from project_kit.cli import main
from project_kit.config import Config
from project_kit.manifest import digest, load_manifest, manifest_path, save_manifest

SKILL = Path(".claude/skills/pk-start/SKILL.md")
TEMPLATE = Path(".project-kit/templates/brief.md")
OLD = b"# an older version\n"


@pytest.fixture
def project(tmp_path, monkeypatch):
    installer.init_project(tmp_path, Config(project_name="demo"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def shipped(rel):
    return dict(installer.iter_assets())[rel]


def as_installed_long_ago(root, rel, content=OLD):
    """The file is `content` and the record says that is what project-kit installed."""
    (root / rel).write_bytes(content)
    manifest = load_manifest(root)
    manifest.files[rel.as_posix()] = digest(content)
    save_manifest(root, manifest, "0.0.1")


def kinds(root, config=None):
    plan = upgrade.build_plan(root, config or Config("demo"))
    return {i.rel: i.kind for i in plan.items if i.kind != upgrade.OK}


# --- init records what it installs ---------------------------------------------------------


def test_init_records_the_digest_of_every_shipped_file(project):
    manifest = load_manifest(project)
    assert manifest.project_kit
    for rel, content in installer.iter_assets():
        assert manifest.recorded(rel) == digest(content), rel


def test_init_does_not_record_a_file_that_differs(tmp_path):
    (tmp_path / SKILL.parent).mkdir(parents=True)
    (tmp_path / SKILL).write_text("mine", encoding="utf-8")
    installer.init_project(tmp_path, Config("demo"))
    assert load_manifest(tmp_path).recorded(SKILL) is None


def test_crlf_is_not_an_edit(project):
    text = (project / TEMPLATE).read_bytes().replace(b"\n", b"\r\n")
    (project / TEMPLATE).write_bytes(text)  # what git's autocrlf does on a Windows checkout
    assert kinds(project) == {}


def test_a_damaged_or_missing_manifest_is_an_empty_one(tmp_path):
    assert load_manifest(tmp_path).files == {}
    manifest_path(tmp_path).parent.mkdir(parents=True)
    manifest_path(tmp_path).write_text("{not json", encoding="utf-8")
    assert load_manifest(tmp_path).files == {}
    manifest_path(tmp_path).write_text(json.dumps({"version": 99, "files": {}}), encoding="utf-8")
    assert load_manifest(tmp_path).files == {}


# --- classification -----------------------------------------------------------------------


def test_a_fresh_project_has_nothing_to_upgrade(project):
    assert kinds(project) == {}


def test_an_untouched_old_file_is_an_update(project):
    as_installed_long_ago(project, SKILL)
    assert kinds(project) == {SKILL: upgrade.UPDATE}


def test_a_missing_file_is_added(project):
    (project / TEMPLATE).unlink()
    assert kinds(project) == {TEMPLATE: upgrade.ADD}


def test_a_file_edited_while_the_package_changed_is_a_conflict(project):
    manifest = load_manifest(project)
    manifest.files[SKILL.as_posix()] = digest(OLD)  # installed an old version...
    save_manifest(project, manifest, "0.0.1")
    (project / SKILL).write_bytes(b"# my edit\n")  # ...which the user then edited
    assert kinds(project) == {SKILL: upgrade.CONFLICT}


def test_an_edit_on_a_file_the_package_did_not_change_is_left_alone(project):
    (project / SKILL).write_bytes(b"# my edit\n")  # recorded digest still equals the shipped one
    assert kinds(project) == {SKILL: upgrade.YOURS}


def test_a_differing_file_with_no_record_is_unknown(project):
    manifest = load_manifest(project)
    del manifest.files[SKILL.as_posix()]
    save_manifest(project, manifest, "0.0.1")
    (project / SKILL).write_bytes(OLD)
    assert kinds(project) == {SKILL: upgrade.UNKNOWN}


def test_files_no_longer_shipped_are_reported_not_deleted(project):
    old_skill = project / ".claude/skills/pk-init/SKILL.md"
    old_skill.parent.mkdir(parents=True)
    old_skill.write_text("gone", encoding="utf-8")
    plan = upgrade.build_plan(project, Config("demo"))
    assert [i.rel for i in plan.of(upgrade.OBSOLETE)] == [Path(".claude/skills/pk-init/SKILL.md")]
    upgrade.apply_plan(project, plan, adopt=False)
    assert old_skill.exists()


def test_the_hook_is_part_of_the_package_only_for_projects_that_asked_for_it(project):
    hook = ai_attribution.HOOK
    assert hook not in [rel for rel, _ in installer.shipped_files(Config("demo"))]
    assert hook in [rel for rel, _ in installer.shipped_files(Config("demo", ai_coauthor=False))]


# --- applying ------------------------------------------------------------------------------


def test_dry_run_changes_nothing(project, capsys):
    as_installed_long_ago(project, SKILL)
    before = (project / SKILL).read_bytes()
    assert main(["upgrade"]) == 0
    out = capsys.readouterr().out
    assert "update" in out and SKILL.as_posix() in out and "--apply" in out
    assert (project / SKILL).read_bytes() == before
    assert not (project / upgrade.UPGRADE_DIR).exists()


def test_apply_updates_an_untouched_file_and_keeps_a_backup(project):
    as_installed_long_ago(project, SKILL)
    assert main(["upgrade", "--apply"]) == 0
    assert (project / SKILL).read_bytes() == shipped(SKILL)
    assert (project / upgrade.BACKUP_DIR / SKILL).read_bytes() == OLD
    assert load_manifest(project).recorded(SKILL) == digest(shipped(SKILL))
    assert kinds(project) == {}  # and a second run has nothing left to do


def test_apply_adds_what_is_missing(project):
    (project / TEMPLATE).unlink()
    main(["upgrade", "--apply"])
    assert (project / TEMPLATE).read_bytes() == shipped(TEMPLATE)


def test_apply_never_overwrites_a_conflict_and_leaves_the_new_version_beside_it(project):
    manifest = load_manifest(project)
    manifest.files[SKILL.as_posix()] = digest(OLD)
    save_manifest(project, manifest, "0.0.1")
    (project / SKILL).write_bytes(b"# my edit\n")
    main(["upgrade", "--apply", "--adopt"])  # --adopt does not apply to files you edited
    assert (project / SKILL).read_bytes() == b"# my edit\n"
    assert (project / upgrade.NEW_DIR / SKILL).read_bytes() == shipped(SKILL)


def test_unknown_files_are_kept_unless_adopted(project):
    manifest = load_manifest(project)
    del manifest.files[SKILL.as_posix()]
    save_manifest(project, manifest, "0.0.1")
    (project / SKILL).write_bytes(OLD)

    main(["upgrade", "--apply"])
    assert (project / SKILL).read_bytes() == OLD
    assert (project / upgrade.NEW_DIR / SKILL).is_file()

    main(["upgrade", "--apply", "--adopt"])
    assert (project / SKILL).read_bytes() == shipped(SKILL)
    assert (project / upgrade.BACKUP_DIR / SKILL).read_bytes() == OLD


def test_a_project_from_before_the_manifest_gets_one_after_upgrading(project):
    manifest_path(project).unlink()
    assert kinds(project) == {}  # everything is identical to the package
    main(["upgrade", "--apply"])
    assert load_manifest(project).recorded(SKILL) == digest(shipped(SKILL))


def test_the_diff_shows_what_would_change(project, capsys):
    as_installed_long_ago(project, SKILL, b"line one\n")
    main(["upgrade", "--diff"])
    out = capsys.readouterr().out
    assert f"--- yours/{SKILL.as_posix()}" in out and "-line one" in out


def test_upgrading_the_hook(tmp_path):
    config = Config("demo", ai_coauthor=False)
    installer.init_project(tmp_path, config)
    as_installed_long_ago(tmp_path, ai_attribution.HOOK, b"#!/bin/sh\nexit 0\n")
    assert kinds(tmp_path, config) == {ai_attribution.HOOK: upgrade.UPDATE}


def test_it_needs_an_initialised_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["upgrade"]) == 1
    assert "upgrade" in capsys.readouterr().err
