"""Client for the GitHub REST API: fetches commits and converts them to domain models."""

import os
from datetime import datetime, timezone
from typing import Any

import requests

from gh_commits.models import Commit

API_URL = "https://api.github.com"
PER_PAGE = 100
TIMEOUT_SECONDS = 10


def read_token() -> str | None:
    """Read the personal access token from GITHUB_TOKEN; None if it is unset or empty.

    Without a token GitHub allows 60 requests per hour, with a token 5000.
    """
    return os.environ.get("GITHUB_TOKEN") or None


def _format_timestamp(moment: datetime) -> str:
    """Format a datetime as the ISO 8601 UTC timestamp GitHub expects."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


class GitHubClient:
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

    def get_commits_page(self, repo: str, since: datetime, until: datetime,
                         branch: str | None = None) -> list[Commit]:
        """Fetch one page (at most 100) of commits for `repo` ("owner/name").

        Only commits between `since` and `until` are returned. Without a
        branch, GitHub uses the repository's default branch.
        """
        params = {
            "since": _format_timestamp(since),
            "until": _format_timestamp(until),
            "per_page": PER_PAGE,
        }
        if branch:
            params["sha"] = branch

        response = self._session.get(
            f"{self._base_url}/repos/{repo}/commits",
            params=params,
            headers=self._headers,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return [_parse_commit(item) for item in response.json()]
