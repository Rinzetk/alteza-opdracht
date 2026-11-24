"""Client for the GitHub REST API: fetches commits and converts them to domain models."""

import os
import re
from collections.abc import Iterator
from datetime import date, datetime, time, timezone
from typing import Any, NoReturn

import requests

from gh_commits.errors import (
    AuthenticationError,
    BranchNotFoundError,
    GitHubError,
    InvalidRepositoryNameError,
    NetworkError,
    RateLimitError,
    RepositoryNotFoundError,
)
from gh_commits.models import Commit

API_URL = "https://api.github.com"
PER_PAGE = 100
TIMEOUT_SECONDS = 10
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# GitHub rules: an owner has letters, digits and hyphens (at most 39);
# a repository name has letters, digits, ".", "_" and "-" (at most 100).
REPO_NAME_PATTERN = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")

HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_TOO_MANY_REQUESTS = 429


def read_token() -> str | None:
    """Read the personal access token from GITHUB_TOKEN; None if it is unset or empty.

    Without a token GitHub allows 60 requests per hour, with a token 5000.
    """
    return os.environ.get("GITHUB_TOKEN") or None


def _validate_repo_name(repo: str) -> None:
    """Raise InvalidRepositoryNameError unless `repo` looks like "owner/repo"."""
    name = repo.partition("/")[2]
    if not REPO_NAME_PATTERN.fullmatch(repo) or name in (".", ".."):
        raise InvalidRepositoryNameError(
            f"Invalid repository name '{repo}': expected the form 'owner/repo'."
        )


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


def _is_rate_limited(response: requests.Response) -> bool:
    """Tell whether a 403/429 response means the rate limit is exhausted."""
    return (response.status_code in (HTTP_FORBIDDEN, HTTP_TOO_MANY_REQUESTS)
            and response.headers.get("X-RateLimit-Remaining") == "0")


def _rate_limit_error(response: requests.Response) -> RateLimitError:
    """Build a RateLimitError, with the reset time from X-RateLimit-Reset if present."""
    reset_header = response.headers.get("X-RateLimit-Reset", "")
    if not reset_header.isdigit():
        return RateLimitError("GitHub API rate limit exceeded.", response.status_code)
    reset_at = datetime.fromtimestamp(int(reset_header), tz=timezone.utc)
    return RateLimitError(
        f"GitHub API rate limit exceeded; it resets at {reset_at:%Y-%m-%d %H:%M:%S} UTC.",
        response.status_code,
        reset_at=reset_at,
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
        An empty repository yields no commits.

        The repository name is validated immediately, so an invalid name
        raises InvalidRepositoryNameError here rather than on the first
        iteration. API errors raise a GitHubError subclass while iterating.
        """
        _validate_repo_name(repo)
        params: dict[str, str | int] = {
            "since": _start_of_day(since),
            "until": _end_of_day(until),
            "per_page": PER_PAGE,
        }
        if branch:
            params["sha"] = branch
        return self._iter_pages(repo, params, branch)

    def _iter_pages(self, repo: str, params: dict[str, str | int],
                    branch: str | None) -> Iterator[Commit]:
        """Follow the Link header from page to page and yield the commits."""
        url: str | None = f"{self._base_url}/repos/{repo}/commits"
        query: dict[str, str | int] | None = params
        while url:
            response = self._get(url, query)
            if response.status_code == HTTP_CONFLICT:
                return  # GitHub answers 409 for an empty repository
            if not response.ok:
                self._raise_for_error(response, repo, branch)
            yield from (_parse_commit(item) for item in response.json())
            url = response.links.get("next", {}).get("url")
            query = None  # the next URL already contains the query

    def _get(self, url: str, params: dict[str, str | int] | None = None) -> requests.Response:
        """Send a GET request; translate connection problems into a NetworkError."""
        try:
            return self._session.get(
                url,
                params=params,
                headers=self._headers,
                timeout=TIMEOUT_SECONDS,
            )
        except (requests.ConnectionError, requests.Timeout) as error:
            raise NetworkError(f"Could not reach GitHub: {error}") from error

    def _raise_for_error(self, response: requests.Response, repo: str,
                         branch: str | None) -> NoReturn:
        """Raise the GitHubError subclass that matches a failed response."""
        status = response.status_code
        if status == HTTP_UNAUTHORIZED:
            raise AuthenticationError(
                "GitHub rejected the token: it is invalid or expired.", status
            )
        if _is_rate_limited(response):
            raise _rate_limit_error(response)
        if status == HTTP_NOT_FOUND:
            # GitHub answers the same 404 for a missing repository and a
            # missing branch, so check the repository to tell them apart.
            if branch and self._repository_exists(repo):
                raise BranchNotFoundError(
                    f"Branch '{branch}' not found in repository '{repo}'.", status
                )
            raise RepositoryNotFoundError(
                f"Repository '{repo}' not found or not accessible.", status
            )
        raise GitHubError(f"GitHub returned HTTP {status} {response.reason}.", status)

    def _repository_exists(self, repo: str) -> bool:
        """Tell whether `repo` exists and is accessible."""
        return self._get(f"{self._base_url}/repos/{repo}").ok
