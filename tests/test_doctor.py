import subprocess

from project_kit import doctor
from project_kit.cli import main
from project_kit.doctor import Status
from project_kit.gh import Gh

AUTH_OK = "github.com\n  - Token scopes: 'gist', 'project', 'read:org', 'repo', 'workflow'\n"
AUTH_NO_PROJECT = "github.com\n  - Token scopes: 'gist', 'repo'\n"
AUTH_NO_SCOPES = "github.com\n  Logged in to github.com account x (GH_TOKEN)\n"


def proc(stdout="", code=0, stderr=""):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)


def fake_gh(*results):
    queue = list(results)

    def runner(cmd, **kwargs):
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    return Gh(retries=0, runner=runner, sleep=lambda s: None)


def by_name(checks):
    return {c.name: c for c in checks}


def test_parse_scopes():
    assert doctor.parse_scopes(AUTH_OK) == ["gist", "project", "read:org", "repo", "workflow"]
    assert doctor.parse_scopes(AUTH_NO_SCOPES) is None


def test_gh_ok_with_required_scopes():
    checks = by_name(doctor.check_gh(fake_gh(proc("gh version 2.1.0\n"), proc(AUTH_OK))))
    assert checks["gh"].status is Status.OK
    assert "2.1.0" in checks["gh"].detail
    assert checks["gh auth"].status is Status.OK


def test_gh_missing_scope_is_blocking_and_explains_fix():
    checks = by_name(doctor.check_gh(fake_gh(proc("gh version 2.1.0"), proc(AUTH_NO_PROJECT))))
    auth = checks["gh auth"]
    assert auth.status is Status.FAIL
    assert "project" in auth.detail
    assert "gh auth refresh -s project" in auth.hint


def test_gh_not_logged_in_is_blocking():
    not_logged = proc(code=1, stderr="You are not logged into any GitHub hosts. Run gh auth login")
    checks = by_name(doctor.check_gh(fake_gh(proc("gh version 2.1.0"), not_logged)))
    assert checks["gh auth"].status is Status.FAIL
    assert "gh auth login" in checks["gh auth"].hint


def test_gh_missing_is_blocking():
    checks = doctor.check_gh(fake_gh(FileNotFoundError()))
    assert [c.name for c in checks] == ["gh"]
    assert checks[0].status is Status.FAIL
    assert "cli.github.com" in checks[0].hint


def test_gh_unverifiable_scopes_is_only_a_warning():
    checks = by_name(doctor.check_gh(fake_gh(proc("gh version 2.1.0"), proc(AUTH_NO_SCOPES))))
    assert checks["gh auth"].status is Status.WARN


def test_git_missing_is_blocking():
    assert doctor.check_git(lambda name: None, subprocess.run).status is Status.FAIL


def test_uv_and_speckit_missing_are_only_warnings(tmp_path):
    never = lambda name: None  # noqa: E731
    assert doctor.check_uv(never, subprocess.run).status is Status.WARN
    check = doctor.check_speckit(never, subprocess.run, tmp_path)
    assert check.status is Status.WARN
    assert "handoff" in check.hint


def test_speckit_detected_by_directory(tmp_path):
    (tmp_path / ".specify").mkdir()
    check = doctor.check_speckit(lambda name: None, subprocess.run, tmp_path)
    assert check.status is Status.OK


def test_exit_code_only_fails_on_blocking_problems():
    ok = doctor.Check("a", Status.OK, "")
    warn = doctor.Check("b", Status.WARN, "")
    fail = doctor.Check("c", Status.FAIL, "")
    assert doctor.exit_code([ok, warn]) == 0
    assert doctor.exit_code([ok, warn, fail]) == 1


def test_render_shows_hint_for_problems_and_summary():
    text = doctor.render([doctor.Check("gh", Status.FAIL, "not found", "install it")])
    assert "[FAIL] gh: not found" in text
    assert "-> install it" in text
    assert "1 blocking problem" in text


def test_cli_doctor_returns_exit_code(monkeypatch, capsys):
    checks = [doctor.Check("git", Status.FAIL, "not found", "install git")]
    monkeypatch.setattr(doctor, "run_checks", lambda: checks)
    assert main(["doctor"]) == 1
    assert "not found" in capsys.readouterr().out
