"""Live tests against the real GitHub API.

They use octocat/Hello-World, a small public repository whose history before
2013 no longer changes. The tests only check what git itself records (names
and messages); logins are left out because accounts can be renamed.

Marked `integration` and skipped without GITHUB_TOKEN, so a normal test run
never depends on the network. Run them with: pytest -m integration
"""

import json
import os

import pytest

from gh_commits.cli import main

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"),
                       reason="live tests need GITHUB_TOKEN"),
]

REPO = "octocat/Hello-World"
RANGE = ["--since", "2011-01-01", "--until", "2012-12-31"]


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    """Keep the cache in a temporary directory, so every run really asks GitHub."""
    monkeypatch.setenv("GH_COMMITS_CACHE_PATH", str(tmp_path))


def test_fetches_and_groups_real_commits(capsys):
    assert main([REPO, *RANGE, "--branch", "master", "--format", "json"]) == 0

    authors = json.loads(capsys.readouterr().out)
    assert {(a["name"], a["commit_count"]) for a in authors} == {
        ("cameronmcefee", 1),
        ("Johnneylee Jack Rollins", 1),
        ("The Octocat", 1),
    }
    messages = [message for author in authors for message in author["messages"]]
    assert "first commit" in messages


def test_text_output_for_the_default_branch(capsys):
    assert main([REPO, *RANGE]) == 0

    output = capsys.readouterr()
    assert output.out.startswith(f"{REPO}, 2011-01-01 to 2012-12-31 (default branch)\n"
                                 "3 commits by 3 authors\n")
    assert output.err == ""


def test_range_without_commits(capsys):
    assert main([REPO, "--since", "2010-01-01", "--until", "2010-12-31"]) == 0

    assert capsys.readouterr().out.endswith("No commits found.\n")


def test_unknown_repository_exits_with_code_1(capsys):
    assert main(["octocat/this-repository-does-not-exist", *RANGE]) == 1

    assert "not found" in capsys.readouterr().err


def test_unknown_branch_exits_with_code_1(capsys):
    assert main([REPO, *RANGE, "--branch", "this-branch-does-not-exist"]) == 1

    assert "Branch 'this-branch-does-not-exist' not found" in capsys.readouterr().err
