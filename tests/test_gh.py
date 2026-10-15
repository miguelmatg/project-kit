import subprocess

import pytest

from project_kit.gh import Gh, GhAuthError, GhError, GhNotFoundError


class FakeRunner:
    """Returns queued results in order and records every command."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def ok(stdout=""):
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


def fail(stderr, code=1):
    return subprocess.CompletedProcess([], code, stdout="", stderr=stderr)


def make(*results, retries=3):
    runner = FakeRunner(*results)
    sleeps = []
    gh = Gh(retries=retries, backoff=1.0, runner=runner, sleep=sleeps.append)
    return gh, runner, sleeps


def test_run_returns_stdout_and_builds_command():
    gh, runner, _ = make(ok("hello"))
    assert gh.run("repo", "view") == "hello"
    assert runner.calls[0][0] == ["gh", "repo", "view"]


def test_json_parses_output():
    gh, _, _ = make(ok('{"a": [1, 2]}'))
    assert gh.json("api", "x") == {"a": [1, 2]}


def test_json_invalid_output_raises():
    gh, _, _ = make(ok("not json"))
    with pytest.raises(GhError, match="valid JSON"):
        gh.json("api", "x")


def test_retries_502_with_exponential_backoff():
    gh, runner, sleeps = make(
        fail("HTTP 502: Bad Gateway"), fail("HTTP 502: Bad Gateway"), ok("done")
    )
    assert gh.run("api", "x") == "done"
    assert len(runner.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_retries_intermittent_graphql_error():
    gh, runner, _ = make(fail("Something went wrong while executing your query"), ok("{}"))
    assert gh.run("api", "graphql") == "{}"
    assert len(runner.calls) == 2


def test_gives_up_after_max_retries():
    gh, runner, sleeps = make(*[fail("HTTP 503") for _ in range(4)], retries=3)
    with pytest.raises(GhError) as exc:
        gh.run("api", "x")
    assert len(runner.calls) == 4
    assert sleeps == [1.0, 2.0, 4.0]
    assert exc.value.returncode == 1


def test_non_transient_error_is_not_retried():
    gh, runner, sleeps = make(fail("HTTP 404: Not Found"))
    with pytest.raises(GhError, match="404"):
        gh.run("api", "x")
    assert len(runner.calls) == 1
    assert sleeps == []


def test_missing_gh_gives_clear_error():
    gh, _, _ = make(FileNotFoundError())
    with pytest.raises(GhNotFoundError, match="cli.github.com"):
        gh.run("--version")


def test_not_authenticated_gives_clear_error_without_retry():
    gh, runner, _ = make(fail("To get started with GitHub CLI, please run:  gh auth login"))
    with pytest.raises(GhAuthError, match="gh auth login"):
        gh.run("repo", "view")
    assert len(runner.calls) == 1


def test_input_is_passed_to_subprocess():
    gh, runner, _ = make(ok("{}"))
    gh.run("api", "graphql", "--input", "-", input='{"query": "x"}')
    assert runner.calls[0][1]["input"] == b'{"query": "x"}'  # sent as bytes, see the test below


def test_stdin_is_sent_byte_for_byte_with_no_newline_translation():
    """Regression: on Windows, text-mode stdin turned every LF into CRLF in issue bodies."""
    import sys

    echo = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"
    gh = Gh(executable=sys.executable, retries=0)
    body = "line one\nline two\n\n- [ ] item\n"
    assert gh.run("-c", echo, input=body) == body


def test_output_with_crlf_is_normalised_to_lf():
    """Bodies typed in GitHub's web editor come back with CRLF; comparisons must not care."""
    import sys

    gh = Gh(executable=sys.executable, retries=0)
    code = "import sys; sys.stdout.buffer.write(bytes([97, 13, 10, 98, 13, 10]))"  # a CRLF b CRLF
    assert gh.run("-c", code) == "a\nb\n"


def test_rate_limit_gets_a_clear_message_and_is_not_retried():
    from project_kit.gh import GhRateLimitError

    gh, runner, sleeps = make(fail("GraphQL: API rate limit exceeded for user ID 1."))
    with pytest.raises(GhRateLimitError, match="Wait a minute"):
        gh.run("api", "graphql")
    assert len(runner.calls) == 1 and sleeps == []


def test_secondary_rate_limit_is_still_retried():
    gh, runner, _ = make(fail("You have exceeded a secondary rate limit."), ok("{}"))
    assert gh.run("api", "x") == "{}"
    assert len(runner.calls) == 2
