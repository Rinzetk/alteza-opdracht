"""Tests for the command-line interface. HTTP calls are mocked with `responses`."""

import json
import runpy
import sys

import pytest
import requests
import responses
from responses import matchers

from gh_commits.cache import CACHE_FILE_NAME
from gh_commits.cli import main

COMMITS_URL = "https://api.github.com/repos/octo/hello/commits"
REPO_URL = "https://api.github.com/repos/octo/hello"
ARGS = ["octo/hello", "--since", "2026-01-01", "--until", "2026-01-31"]
QUERY = {"since": "2026-01-01T00:00:00Z", "until": "2026-01-31T23:59:59Z", "per_page": "100"}
FAR_FUTURE = "9999999999"


def api_commit(sha, name, email, login, message):
    """Build one commit as it appears in the GitHub API response."""
    return {
        "sha": sha,
        "commit": {
            "author": {"name": name, "email": email, "date": "2026-01-15T12:00:00Z"},
            "message": message,
        },
        "author": {"login": login} if login else None,
    }


COMMITS = [
    api_commit("a1", "Ada Lovelace", "ada@example.com", "ada", "Add engine\n\nWith details."),
    api_commit("b1", "Bob", "bob@example.com", None, "Fix typo"),
    api_commit("a2", "Ada Lovelace", "ada@example.com", "ada", "Add tests"),
]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """Keep the cache in a temporary directory and start without a token."""
    monkeypatch.setenv("GH_COMMITS_CACHE_PATH", str(tmp_path))
    monkeypatch.delenv("GH_COMMITS_CACHE_TTL", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


def assert_exits_with(code, argv):
    """Assert that argparse stops main() with the given exit code."""
    with pytest.raises(SystemExit) as caught:
        main(argv)
    assert caught.value.code == code


@responses.activate
def test_text_output_shows_count_and_subjects_per_author(capsys):
    responses.get(COMMITS_URL, json=COMMITS)

    assert main(ARGS) == 0

    assert capsys.readouterr().out == (
        "octo/hello, 2026-01-01 to 2026-01-31 (default branch)\n"
        "3 commits by 2 authors\n"
        "\n"
        "Ada Lovelace (@ada) <ada@example.com>: 2 commits\n"
        "  - Add engine\n"
        "  - Add tests\n"
        "\n"
        "Bob <bob@example.com>: 1 commit\n"
        "  - Fix typo\n"
    )


@responses.activate
def test_json_output_has_full_messages(capsys):
    responses.get(COMMITS_URL, json=COMMITS)

    assert main([*ARGS, "--format", "json"]) == 0

    assert json.loads(capsys.readouterr().out) == [
        {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "login": "ada",
            "commit_count": 2,
            "messages": ["Add engine\n\nWith details.", "Add tests"],
        },
        {
            "name": "Bob",
            "email": "bob@example.com",
            "login": None,
            "commit_count": 1,
            "messages": ["Fix typo"],
        },
    ]


@responses.activate
def test_branch_is_sent_and_shown(capsys):
    responses.get(COMMITS_URL, json=[],
                  match=[matchers.query_param_matcher({**QUERY, "sha": "main"})])

    assert main([*ARGS, "--branch", "main"]) == 0

    assert "(branch: main)" in capsys.readouterr().out


@responses.activate
def test_without_branch_uses_the_default_branch():
    responses.get(COMMITS_URL, json=[], match=[matchers.query_param_matcher(QUERY)])

    assert main(ARGS) == 0


@responses.activate
def test_no_commits_says_so(capsys):
    responses.get(COMMITS_URL, json=[])

    assert main(ARGS) == 0

    assert capsys.readouterr().out.endswith("No commits found.\n")


@responses.activate
def test_no_commits_as_json_is_an_empty_list(capsys):
    responses.get(COMMITS_URL, json=[])

    assert main([*ARGS, "--format", "json"]) == 0

    assert json.loads(capsys.readouterr().out) == []


@responses.activate
def test_empty_commit_message_is_shown_as_empty_subject(capsys):
    responses.get(COMMITS_URL, json=[api_commit("a1", "Ada", "ada@example.com", "ada", "")])

    assert main(ARGS) == 0

    assert capsys.readouterr().out.endswith("Ada (@ada) <ada@example.com>: 1 commit\n  - \n")


@responses.activate
def test_single_day_range_is_allowed():
    responses.get(COMMITS_URL, json=[])

    assert main(["octo/hello", "--since", "2026-01-01", "--until", "2026-01-01"]) == 0


@pytest.mark.parametrize("argv", [
    ["octo/hello", "--since", "2026/01/01", "--until", "2026-01-31"],
    ["octo/hello", "--since", "20260101", "--until", "2026-01-31"],
    ["octo/hello", "--since", "2026-02-30", "--until", "2026-03-31"],
    ["octo/hello", "--since", "2026-01-31", "--until", "2026-01-01"],
    ["octo/hello", "--since", "2026-01-01"],
    ["--since", "2026-01-01", "--until", "2026-01-31"],
    [*ARGS, "--format", "xml"],
    [*ARGS, "--no-cache", "--clear-cache"],
])
@responses.activate
def test_invalid_arguments_exit_with_code_2(argv):
    assert_exits_with(2, argv)

    assert not responses.calls


def test_until_before_since_explains_why(capsys):
    assert_exits_with(2, ["octo/hello", "--since", "2026-01-31", "--until", "2026-01-01"])

    assert "--until must not be before --since" in capsys.readouterr().err


@responses.activate
def test_invalid_repository_name_exits_with_code_2(capsys):
    assert main(["not a repo", "--since", "2026-01-01", "--until", "2026-01-31"]) == 2

    assert "Invalid repository name" in capsys.readouterr().err
    assert not responses.calls


def test_invalid_cache_ttl_exits_with_code_2(monkeypatch, capsys):
    monkeypatch.setenv("GH_COMMITS_CACHE_TTL", "soon")

    assert main(ARGS) == 2

    assert "GH_COMMITS_CACHE_TTL" in capsys.readouterr().err


@pytest.mark.parametrize("status, headers, expected", [
    (401, {}, "invalid or expired"),
    (404, {}, "not found"),
    (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": FAR_FUTURE}, "rate limit"),
    (500, {}, "HTTP 500"),
])
@responses.activate
def test_api_errors_exit_with_code_1_and_a_message_on_stderr(capsys, status, headers,
                                                             expected):
    responses.get(COMMITS_URL, status=status, headers=headers)

    assert main(ARGS) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.startswith("gh-commits: error: ")
    assert expected in output.err


@responses.activate
def test_missing_branch_exits_with_code_1(capsys):
    responses.get(COMMITS_URL, status=404)
    responses.get(REPO_URL, json={"full_name": "octo/hello"})

    assert main([*ARGS, "--branch", "nope"]) == 1

    assert "Branch 'nope' not found" in capsys.readouterr().err


@responses.activate
def test_network_error_exits_with_code_1(capsys):
    responses.get(COMMITS_URL, body=requests.ConnectionError("connection refused"))

    assert main(ARGS) == 1

    assert "Could not reach GitHub" in capsys.readouterr().err


@responses.activate
def test_responses_are_cached_between_runs():
    responses.get(COMMITS_URL, json=COMMITS)

    main(ARGS)
    main(ARGS)

    assert len(responses.calls) == 1


@responses.activate
def test_no_cache_always_asks_github_and_writes_no_cache(tmp_path):
    responses.get(COMMITS_URL, json=COMMITS)

    main([*ARGS, "--no-cache"])
    main([*ARGS, "--no-cache"])

    assert len(responses.calls) == 2
    assert not (tmp_path / CACHE_FILE_NAME).exists()


@responses.activate
def test_clear_cache_fetches_again():
    responses.get(COMMITS_URL, json=COMMITS)

    main(ARGS)
    main([*ARGS, "--clear-cache"])

    assert len(responses.calls) == 2


@responses.activate
def test_token_is_sent_but_never_printed(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    responses.get(COMMITS_URL, status=401,
                  match=[matchers.header_matcher({"Authorization": "Bearer secret-token"})])

    assert main(ARGS) == 1

    output = capsys.readouterr()
    assert "secret-token" not in output.out + output.err


def test_runs_as_module(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["gh-commits", "--help"])

    with pytest.raises(SystemExit) as caught:
        runpy.run_module("gh_commits", run_name="__main__")

    assert caught.value.code == 0
    assert "usage: gh-commits" in capsys.readouterr().out
