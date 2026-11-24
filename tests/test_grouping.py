"""Tests for grouping commits by author."""

from datetime import datetime, timezone

from gh_commits.grouping import group_by_author
from gh_commits.models import AuthorSummary, Commit


def make_commit(
    sha="abc123",
    name="Ada Lovelace",
    email="ada@example.com",
    login="ada",
    message="First commit",
):
    """Build a Commit with defaults, so each test only states what matters to it."""
    return Commit(
        sha=sha,
        author_name=name,
        author_email=email,
        author_login=login,
        date=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        message=message,
    )


def test_empty_list_returns_empty_list():
    assert group_by_author([]) == []


def test_single_author():
    commits = [
        make_commit(sha="1", message="First"),
        make_commit(sha="2", message="Second"),
    ]

    result = group_by_author(commits)

    assert result == [
        AuthorSummary(
            name="Ada Lovelace",
            email="ada@example.com",
            login="ada",
            messages=("First", "Second"),
        )
    ]
    assert result[0].commit_count == 2


def test_multiple_authors_sorted_by_commit_count():
    commits = [
        make_commit(sha="1", name="Ada", login="ada", message="a1"),
        make_commit(sha="2", name="Linus", email="linus@example.com", login="linus",
                    message="l1"),
        make_commit(sha="3", name="Linus", email="linus@example.com", login="linus",
                    message="l2"),
        make_commit(sha="4", name="Linus", email="linus@example.com", login="linus",
                    message="l3"),
        make_commit(sha="5", name="Grace", email="grace@example.com", login="grace",
                    message="g1"),
        make_commit(sha="6", name="Grace", email="grace@example.com", login="grace",
                    message="g2"),
    ]

    result = group_by_author(commits)

    assert [(s.login, s.commit_count) for s in result] == [
        ("linus", 3),
        ("grace", 2),
        ("ada", 1),
    ]
    assert result[0].messages == ("l1", "l2", "l3")


def test_equal_commit_count_is_sorted_by_name():
    commits = [
        make_commit(sha="1", name="bob", email="bob@example.com", login="bob"),
        make_commit(sha="2", name="Alice", email="alice@example.com", login="alice"),
    ]

    result = group_by_author(commits)

    assert [s.name for s in result] == ["Alice", "bob"]


def test_author_without_login_is_grouped_by_name_and_email():
    commits = [
        make_commit(sha="1", name="Anonymous", email="anon@example.com", login=None,
                    message="x1"),
        make_commit(sha="2", name="Anonymous", email="anon@example.com", login=None,
                    message="x2"),
    ]

    result = group_by_author(commits)

    assert result == [
        AuthorSummary(
            name="Anonymous",
            email="anon@example.com",
            login=None,
            messages=("x1", "x2"),
        )
    ]


def test_without_login_same_name_different_email_are_separate_authors():
    commits = [
        make_commit(sha="1", name="John", email="john@work.example", login=None),
        make_commit(sha="2", name="John", email="john@home.example", login=None),
    ]

    assert len(group_by_author(commits)) == 2


def test_same_login_with_different_emails_is_one_author():
    commits = [
        make_commit(sha="1", email="ada@work.example", login="ada"),
        make_commit(sha="2", email="ada@home.example", login="ada"),
    ]

    result = group_by_author(commits)

    assert len(result) == 1
    assert result[0].commit_count == 2


def test_author_with_and_without_login_are_separate_authors():
    commits = [
        make_commit(sha="1", login="ada"),
        make_commit(sha="2", login=None),
    ]

    assert len(group_by_author(commits)) == 2
