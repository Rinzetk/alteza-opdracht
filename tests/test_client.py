"""Tests for the GitHub API client. HTTP calls are mocked with `responses`."""

from datetime import date, datetime, timezone

import pytest
import requests
import responses
from responses import matchers

from gh_commits.client import GitHubClient, read_token
from gh_commits.models import Commit

COMMITS_URL = "https://api.github.com/repos/octo/hello/commits"
SINCE = date(2026, 1, 1)
UNTIL = date(2026, 1, 31)
FIRST_PAGE_QUERY = {
    "since": "2026-01-01T00:00:00Z",
    "until": "2026-01-31T23:59:59Z",
    "per_page": "100",
}


def api_commit(sha="abc123", name="Ada Lovelace", email="ada@example.com",
               login="ada", date="2026-01-15T12:00:00Z", message="First commit"):
    """Build one commit as it appears in the GitHub API response."""
    return {
        "sha": sha,
        "commit": {
            "author": {"name": name, "email": email, "date": date},
            "message": message,
        },
        "author": {"login": login} if login else None,
    }


def page_url(page, **query):
    """Build the URL GitHub puts in the Link header for a follow-up page."""
    params = "&".join(f"{key}={value}" for key, value in {**query, "page": page}.items())
    return f"{COMMITS_URL}?{params}"


def link_header(next_url):
    """Build a Link header that points to the next page."""
    return {"Link": f'<{next_url}>; rel="next"'}


def register_pages(pages, query):
    """Register `pages` (lists of commits) as one paginated response chain."""
    for number, commits in enumerate(pages, start=1):
        page_query = query if number == 1 else {**query, "page": str(number)}
        is_last = number == len(pages)
        responses.get(
            COMMITS_URL,
            json=commits,
            headers={} if is_last else link_header(page_url(number + 1, **query)),
            match=[matchers.query_param_matcher(page_query)],
        )


@pytest.fixture(name="client")
def fixture_client():
    return GitHubClient(requests.Session())


@responses.activate
def test_converts_json_to_commit_objects(client):
    responses.get(COMMITS_URL, json=[api_commit()])

    result = list(client.iter_commits("octo/hello", SINCE, UNTIL))

    assert result == [
        Commit(
            sha="abc123",
            author_name="Ada Lovelace",
            author_email="ada@example.com",
            author_login="ada",
            date=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            message="First commit",
        )
    ]


@responses.activate
def test_commit_without_github_account_has_no_login(client):
    responses.get(COMMITS_URL, json=[api_commit(login=None)])

    result = list(client.iter_commits("octo/hello", SINCE, UNTIL))

    assert result[0].author_login is None


@responses.activate
def test_empty_result_returns_no_commits_with_one_request(client):
    responses.get(COMMITS_URL, json=[])

    assert not list(client.iter_commits("octo/hello", SINCE, UNTIL))
    assert len(responses.calls) == 1


@responses.activate
def test_follows_link_header_across_multiple_pages(client):
    register_pages(
        [
            [api_commit(sha="a1"), api_commit(sha="a2")],
            [api_commit(sha="b1")],
            [api_commit(sha="c1")],
        ],
        FIRST_PAGE_QUERY,
    )

    result = list(client.iter_commits("octo/hello", SINCE, UNTIL))

    assert [commit.sha for commit in result] == ["a1", "a2", "b1", "c1"]
    assert len(responses.calls) == 3


@responses.activate
def test_fetches_next_page_only_when_needed(client):
    register_pages([[api_commit(sha="a1")], [api_commit(sha="b1")]], FIRST_PAGE_QUERY)

    commits = client.iter_commits("octo/hello", SINCE, UNTIL)

    assert next(commits).sha == "a1"
    assert len(responses.calls) == 1
    assert next(commits).sha == "b1"
    assert len(responses.calls) == 2


@responses.activate
def test_branch_is_sent_and_kept_across_pages(client):
    register_pages(
        [[api_commit(sha="a1")], [api_commit(sha="b1")]],
        {**FIRST_PAGE_QUERY, "sha": "main"},
    )

    result = list(client.iter_commits("octo/hello", SINCE, UNTIL, branch="main"))

    assert [commit.sha for commit in result] == ["a1", "b1"]


@responses.activate
def test_without_branch_sends_no_sha(client):
    responses.get(
        COMMITS_URL,
        json=[],
        match=[matchers.query_param_matcher(FIRST_PAGE_QUERY)],
    )

    list(client.iter_commits("octo/hello", SINCE, UNTIL))


@responses.activate
def test_single_day_range_covers_the_whole_day_in_utc(client):
    responses.get(
        COMMITS_URL,
        json=[],
        match=[matchers.query_param_matcher({
            "since": "2026-03-15T00:00:00Z",
            "until": "2026-03-15T23:59:59Z",
            "per_page": "100",
        })],
    )

    day = date(2026, 3, 15)
    list(client.iter_commits("octo/hello", day, day))


@responses.activate
def test_sends_token_as_authorization_header():
    responses.get(
        COMMITS_URL,
        json=[],
        match=[matchers.header_matcher({"Authorization": "Bearer secret-token"})],
    )

    list(GitHubClient(requests.Session(), token="secret-token").iter_commits(
        "octo/hello", SINCE, UNTIL
    ))


@responses.activate
def test_without_token_sends_no_authorization_header(client):
    responses.get(COMMITS_URL, json=[])

    list(client.iter_commits("octo/hello", SINCE, UNTIL))

    assert "Authorization" not in responses.calls[0].request.headers


@responses.activate
def test_uses_the_injected_session():
    session = requests.Session()
    session.headers["X-Test"] = "injected"
    responses.get(COMMITS_URL, json=[])

    list(GitHubClient(session).iter_commits("octo/hello", SINCE, UNTIL))

    assert responses.calls[0].request.headers["X-Test"] == "injected"


def test_read_token_from_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

    assert read_token() == "secret-token"


def test_read_token_missing_returns_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    assert read_token() is None


def test_read_token_empty_returns_none(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "")

    assert read_token() is None
