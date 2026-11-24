"""Command-line interface: parse arguments, fetch commits and print them per author.

Exit codes: 0 = success, 1 = GitHub API error, 2 = invalid input.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date, datetime

import requests

from gh_commits.cache import build_session
from gh_commits.client import GitHubClient, mount_retries, read_token
from gh_commits.errors import GitHubError, InvalidRepositoryNameError
from gh_commits.grouping import group_by_author
from gh_commits.models import AuthorSummary

EXIT_OK = 0
EXIT_API_ERROR = 1
EXIT_INVALID_INPUT = 2
DATE_FORMAT = "%Y-%m-%d"
PROG = "gh-commits"


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date for argparse; other formats are rejected."""
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}': expected YYYY-MM-DD"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Fetch the commits of a GitHub repository within a date range "
                    "and group them by author.",
        epilog="Set GITHUB_TOKEN to raise the rate limit from 60 to 5000 requests per hour.",
    )
    parser.add_argument("repository", help='repository as "owner/repo", e.g. python/cpython')
    parser.add_argument("--since", required=True, type=_parse_date, metavar="DATE",
                        help="start date (YYYY-MM-DD), inclusive")
    parser.add_argument("--until", required=True, type=_parse_date, metavar="DATE",
                        help="end date (YYYY-MM-DD), inclusive")
    parser.add_argument("--branch",
                        help="branch to search; defaults to the repository's default branch")
    parser.add_argument("--format", choices=("text", "json"), default="text",
                        help="output format (default: text)")
    cache_options = parser.add_mutually_exclusive_group()
    cache_options.add_argument("--no-cache", action="store_true",
                               help="skip the cache for this call")
    cache_options.add_argument("--clear-cache", action="store_true",
                               help="clear the cache before the call")
    return parser


def _create_session(args: argparse.Namespace) -> requests.Session:
    """Build the HTTP session the options ask for; both kinds retry transient failures."""
    if args.no_cache:
        return mount_retries(requests.Session())
    session = build_session()
    if args.clear_cache:
        session.cache.clear()
    return session


def _subject(message: str) -> str:
    """Return the first line of a commit message."""
    return (message.splitlines() or [""])[0]


def _count(number: int, noun: str) -> str:
    """Return e.g. "1 commit" or "2 commits"."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _author_label(summary: AuthorSummary) -> str:
    """Return the author as "Name (@login) <email>"; the login only when known."""
    login = f" (@{summary.login})" if summary.login else ""
    return f"{summary.name}{login} <{summary.email}>"


def format_text(summaries: list[AuthorSummary], repository: str, since: date,
                until: date, branch: str | None) -> str:
    """Format the summaries as readable text: per author the count and message subjects."""
    branch_label = f"branch: {branch}" if branch else "default branch"
    lines = [f"{repository}, {since} to {until} ({branch_label})"]
    if not summaries:
        lines.append("No commits found.")
        return "\n".join(lines)

    total = sum(summary.commit_count for summary in summaries)
    lines.append(f"{_count(total, 'commit')} by {_count(len(summaries), 'author')}")
    for summary in summaries:
        lines.append("")
        lines.append(f"{_author_label(summary)}: {_count(summary.commit_count, 'commit')}")
        lines.extend(f"  - {_subject(message)}" for message in summary.messages)
    return "\n".join(lines)


def format_json(summaries: list[AuthorSummary]) -> str:
    """Format the summaries as a JSON list of authors, with the full messages."""
    return json.dumps(
        [
            {
                "name": summary.name,
                "email": summary.email,
                "login": summary.login,
                "commit_count": summary.commit_count,
                "messages": list(summary.messages),
            }
            for summary in summaries
        ],
        indent=2,
        ensure_ascii=False,
    )


def _fail(message: str, exit_code: int) -> int:
    """Print an error message to stderr and return the exit code."""
    print(f"{PROG}: error: {message}", file=sys.stderr)
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit code.

    Invalid arguments make argparse print the usage and exit with code 2.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.until < args.since:
        parser.error("--until must not be before --since")

    try:
        session = _create_session(args)
    except ValueError as error:  # an invalid GH_COMMITS_CACHE_TTL
        return _fail(str(error), EXIT_INVALID_INPUT)

    with session:
        client = GitHubClient(session, token=read_token())
        try:
            commits = client.iter_commits(args.repository, args.since, args.until, args.branch)
            summaries = group_by_author(commits)
        except InvalidRepositoryNameError as error:
            return _fail(str(error), EXIT_INVALID_INPUT)
        except GitHubError as error:
            return _fail(str(error), EXIT_API_ERROR)

    if args.format == "json":
        print(format_json(summaries))
    else:
        print(format_text(summaries, args.repository, args.since, args.until, args.branch))
    return EXIT_OK
