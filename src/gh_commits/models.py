"""Domain models: a commit and the per-author summary."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Commit:
    """A single commit, with the author details as returned by GitHub.

    `author_login` is None when the commit's email address is not linked
    to a GitHub account.
    """

    sha: str
    author_name: str
    author_email: str
    author_login: str | None
    date: datetime
    message: str


@dataclass(frozen=True)
class AuthorSummary:
    """The commits of one author: who they are and which messages belong to them."""

    name: str
    email: str
    login: str | None
    messages: tuple[str, ...]

    @property
    def commit_count(self) -> int:
        """The number of commits by this author."""
        return len(self.messages)
