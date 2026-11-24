"""Exception hierarchy for errors while talking to the GitHub API."""

from datetime import datetime


class GitHubError(Exception):
    """Base class for all GitHub API errors.

    `status_code` is the HTTP status of the failed response, or None when
    no response was received (for example on a network error).
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(GitHubError):
    """The token was rejected (401): it is invalid or expired."""


class RepositoryNotFoundError(GitHubError):
    """The repository does not exist or is not accessible (404)."""


class BranchNotFoundError(GitHubError):
    """The repository exists, but the requested branch does not (404)."""


class RateLimitError(GitHubError):
    """The rate limit is exhausted (403/429 with X-RateLimit-Remaining: 0).

    `reset_at` is the moment (UTC) the limit resets, or None if GitHub did
    not say.
    """

    def __init__(self, message: str, status_code: int | None = None,
                 reset_at: datetime | None = None):
        super().__init__(message, status_code)
        self.reset_at = reset_at


class NetworkError(GitHubError):
    """GitHub could not be reached: a connection error or a timeout."""


class InvalidRepositoryNameError(ValueError):
    """The repository name is not in the form "owner/repo".

    This is invalid user input, not an API error, so it is deliberately not
    a GitHubError.
    """
