"""Group commits by author. This module does no I/O."""

from collections.abc import Iterable

from gh_commits.models import AuthorSummary, Commit

AuthorKey = tuple[str, ...]


def _author_key(commit: Commit) -> AuthorKey:
    """Determine which author a commit belongs to.

    By login when it is known; otherwise by the name and email address from
    the commit itself. Logins and email addresses are compared case-insensitively.
    """
    if commit.author_login:
        return ("login", commit.author_login.lower())
    return ("anonymous", commit.author_name, commit.author_email.lower())


def group_by_author(commits: Iterable[Commit]) -> list[AuthorSummary]:
    """Group commits by author.

    Sorted by number of commits (most first), ties broken by name.
    An author's name and email address come from their first commit in the
    input; messages keep the order of the input.
    """
    first_commit: dict[AuthorKey, Commit] = {}
    messages: dict[AuthorKey, list[str]] = {}

    for commit in commits:
        key = _author_key(commit)
        first_commit.setdefault(key, commit)
        messages.setdefault(key, []).append(commit.message)

    summaries = [
        AuthorSummary(
            name=first.author_name,
            email=first.author_email,
            login=first.author_login,
            messages=tuple(messages[key]),
        )
        for key, first in first_commit.items()
    ]
    return sorted(summaries, key=lambda s: (-s.commit_count, s.name.casefold()))
