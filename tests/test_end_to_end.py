"""End-to-end tests: main() through every layer, with only the GitHub API mocked.

Each test runs the real CLI, cached session, client, pagination, grouping and
output formatting together. test_cli.py covers the CLI options one by one;
these tests cover scenarios where the layers have to work together.
"""

import functools
import json

import pytest
import responses
from responses import matchers

from gh_commits import cli
from gh_commits.client import GitHubClient, RateLimitPolicy

COMMITS_URL = "https://api.github.com/repos/octo/hello/commits"
ARGS = ["octo/hello", "--since", "2026-01-01", "--until", "2026-01-31"]
QUERY = {"since": "2026-01-01T00:00:00Z", "until": "2026-01-31T23:59:59Z", "per_page": "100"}
NOW = 1767222000  # the fixed clock: 2025-12-31 23:00:00 UTC


def api_commit(sha, name, login, message):
    """Build one commit as it appears in the GitHub API response."""
    return {
        "sha": sha,
        "commit": {
            "author": {"name": name, "email": f"{name.lower()}@example.com",
                       "date": "2026-01-15T12:00:00Z"},
            "message": message,
        },
        "author": {"login": login} if login else None,
    }


PAGE_1 = [
    api_commit("a1", "Ada", "ada", "Add engine"),
    api_commit("b1", "Bob", None, "Fix typo"),
]
PAGE_2 = [
    api_commit("a2", "Ada", "ada", "Add tests"),
    api_commit("c1", "Cleo", "cleo", "Update docs"),
]
PAGE_3 = [
    api_commit("a3", "Ada", "ada", "Release 1.0"),
]

EXPECTED_TEXT = (
    "octo/hello, 2026-01-01 to 2026-01-31 (default branch)\n"
    "5 commits by 3 authors\n"
    "\n"
    "Ada (@ada) <ada@example.com>: 3 commits\n"
    "  - Add engine\n"
    "  - Add tests\n"
    "  - Release 1.0\n"
    "\n"
    "Bob <bob@example.com>: 1 commit\n"
    "  - Fix typo\n"
    "\n"
    "Cleo (@cleo) <cleo@example.com>: 1 commit\n"
    "  - Update docs\n"
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """Keep the cache in a temporary directory and start without a token."""
    monkeypatch.setenv("GH_COMMITS_CACHE_PATH", str(tmp_path))
    monkeypatch.delenv("GH_COMMITS_CACHE_TTL", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


@pytest.fixture(name="sleeps")
def fixture_sleeps(monkeypatch):
    """Make the CLI's client record rate-limit waits instead of really sleeping."""
    recorded = []
    policy = RateLimitPolicy(sleep=recorded.append, clock=lambda: NOW)
    monkeypatch.setattr(cli, "GitHubClient",
                        functools.partial(GitHubClient, rate_limit=policy))
    return recorded


def page_query(number, extra=None):
    """The query of page `number`; GitHub adds `page` to the follow-up URLs."""
    query = {**QUERY, **(extra or {})}
    return query if number == 1 else {**query, "page": str(number)}


def next_link(number, extra=None):
    """A Link header that points to page `number`."""
    params = "&".join(f"{key}={value}" for key, value in page_query(number, extra).items())
    return {"Link": f'<{COMMITS_URL}?{params}>; rel="next"'}


def register_page(number, commits, last, extra=None, **kwargs):
    """Register one page of the paginated commits response."""
    responses.get(
        COMMITS_URL,
        json=commits,
        headers={} if last else next_link(number + 1, extra),
        match=[matchers.query_param_matcher(page_query(number, extra)),
               *kwargs.pop("match", [])],
        **kwargs,
    )


def register_three_pages(extra=None, **kwargs):
    """Register PAGE_1 to PAGE_3 as one paginated response chain."""
    for number, commits in enumerate((PAGE_1, PAGE_2, PAGE_3), start=1):
        register_page(number, commits, last=number == 3, extra=extra, **kwargs)


@responses.activate
def test_authors_are_grouped_across_pages(capsys):
    register_three_pages()

    assert cli.main(ARGS) == 0

    output = capsys.readouterr()
    assert output.out == EXPECTED_TEXT
    assert output.err == ""
    assert len(responses.calls) == 3


@responses.activate
def test_second_run_is_served_from_the_cache(capsys):
    register_three_pages()
    cli.main(ARGS)
    first_output = capsys.readouterr().out

    assert cli.main(ARGS) == 0

    assert capsys.readouterr().out == first_output
    assert len(responses.calls) == 3  # all three pages came from the cache


@responses.activate
def test_branch_and_token_are_sent_on_every_page_and_json_is_complete(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    register_three_pages(
        extra={"sha": "main"},
        match=[matchers.header_matcher({"Authorization": "Bearer secret-token"})],
    )

    assert cli.main([*ARGS, "--branch", "main", "--format", "json"]) == 0

    authors = json.loads(capsys.readouterr().out)
    assert [(a["name"], a["commit_count"]) for a in authors] == [
        ("Ada", 3), ("Bob", 1), ("Cleo", 1),
    ]
    assert authors[0]["messages"] == ["Add engine", "Add tests", "Release 1.0"]


@responses.activate
def test_rate_limit_halfway_is_waited_out(sleeps, capsys):
    register_page(1, PAGE_1, last=False)
    responses.get(
        COMMITS_URL,
        status=403,
        json={"message": "secondary rate limit"},
        headers={"Retry-After": "30"},
        match=[matchers.query_param_matcher(page_query(2))],
    )
    register_page(2, PAGE_2, last=False)
    register_page(3, PAGE_3, last=True)

    assert cli.main(ARGS) == 0

    assert capsys.readouterr().out == EXPECTED_TEXT
    assert sleeps == [31]  # Retry-After plus the safety margin


@responses.activate
def test_rate_limit_halfway_that_lasts_too_long_stops_with_code_1(sleeps, capsys):
    register_page(1, PAGE_1, last=False)
    responses.get(
        COMMITS_URL,
        status=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(NOW + 3600)},
        match=[matchers.query_param_matcher(page_query(2))],
    )

    assert cli.main(ARGS) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert "rate limit" in output.err
    assert not sleeps


@responses.activate
def test_error_on_a_later_page_prints_no_partial_result(capsys):
    register_page(1, PAGE_1, last=False)
    responses.get(COMMITS_URL, status=500,
                  match=[matchers.query_param_matcher(page_query(2))])

    assert cli.main(ARGS) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "gh-commits: error: GitHub returned HTTP 500 Internal Server Error.\n"
