"""Client for the GitHub REST API: fetches commits and converts them to domain models."""

import os
from collections.abc import Iterator
from datetime import date, datetime, time, timezone
from typing import Any

import requests

from gh_commits.models import Commit

API_URL = "https://api.github.com"
PER_PAGE = 100
TIMEOUT_SECONDS = 10
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def read_token() -> str | None:
    """Read the personal access token from GITHUB_TOKEN; None if it is unset or empty.

    Without a token GitHub allows 60 requests per hour, with a token 5000.
    """
    return os.environ.get("GITHUB_TOKEN") or None


def _start_of_day(day: date) -> str:
    """Return the first second of `day` in UTC as an ISO 8601 timestamp."""
    return datetime.combine(day, time.min, tzinfo=timezone.utc).strftime(TIMESTAMP_FORMAT)


def _end_of_day(day: date) -> str:
    """Return the last second of `day` in UTC as an ISO 8601 timestamp.

    This makes the end date inclusive. Git timestamps have whole seconds,
    so 23:59:59 covers the entire day.
    """
    last_second = time(23, 59, 59)
    return datetime.combine(day, last_second, tzinfo=timezone.utc).strftime(TIMESTAMP_FORMAT)


def _parse_commit(item: dict[str, Any]) -> Commit:
    """Convert one commit from the API response into a Commit.

    The top-level `author` is null when the commit's email address is not
    linked to a GitHub account; the login is then None.
    """
    git_author = item["commit"]["author"]
    github_account = item.get("author")
    return Commit(
        sha=item["sha"],
        author_name=git_author["name"],
        author_email=git_author["email"],
        author_login=github_account["login"] if github_account else None,
        date=datetime.fromisoformat(git_author["date"]),
        message=item["commit"]["message"],
    )


# A small public API is intended: one entry point (iter_commits) on top of
# shared state (session, headers). Error handling and retries stay private.
class GitHubClient:  # pylint: disable=too-few-public-methods
    """Fetches commits from the GitHub REST API.

    The HTTP session is passed in rather than created here, so callers can
    plug in caching or a test double without changing the client.
    """

    def __init__(self, session: requests.Session, token: str | None = None,
                 base_url: str = API_URL):
        self._session = session
        self._base_url = base_url
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def iter_commits(self, repo: str, since: date, until: date,
                     branch: str | None = None) -> Iterator[Commit]:
        """Yield all commits for `repo` ("owner/name") from `since` up to and including `until`.

        Both dates are interpreted in UTC. Without a branch, GitHub uses the
        repository's default branch. Pages are fetched lazily: the next page
        is only requested once the commits of the current page are consumed.
        """
        url: str | None = f"{self._base_url}/repos/{repo}/commits"
        params: dict[str, str | int] | None = {
            "since": _start_of_day(since),
            "until": _end_of_day(until),
            "per_page": PER_PAGE,
        }
        if branch:
            params["sha"] = branch

        while url:
            response = self._session.get(
                url,
                params=params,
                headers=self._headers,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            yield from (_parse_commit(item) for item in response.json())
            url = response.links.get("next", {}).get("url")
            params = None  # the next URL already contains the query
