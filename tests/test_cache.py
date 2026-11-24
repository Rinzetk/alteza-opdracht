"""Tests for the cached session. HTTP calls are mocked with `responses`."""

from datetime import date
from pathlib import Path

import pytest
import responses

from gh_commits.cache import (
    CACHE_FILE_NAME,
    DEFAULT_EXPIRE_AFTER_SECONDS,
    build_session,
    cache_dir_from_env,
    expire_after_from_env,
)
from gh_commits.client import GitHubClient

COMMITS_URL = "https://api.github.com/repos/octo/hello/commits"


@pytest.fixture(name="session")
def fixture_session(tmp_path):
    session = build_session(tmp_path, expire_after=3600)
    yield session
    session.close()


@responses.activate
def test_second_identical_call_comes_from_cache(session):
    responses.get(COMMITS_URL, json=[])

    first = session.get(COMMITS_URL)
    second = session.get(COMMITS_URL)

    assert first.from_cache is False
    assert second.from_cache is True
    assert len(responses.calls) == 1


@responses.activate
def test_client_reuses_cached_responses(session):
    responses.get(COMMITS_URL, json=[])
    client = GitHubClient(session)

    for _ in range(2):
        list(client.iter_commits("octo/hello", date(2026, 1, 1), date(2026, 1, 31)))

    assert len(responses.calls) == 1


@pytest.mark.parametrize("status", [403, 404, 500])
@responses.activate
def test_error_responses_are_not_cached(session, status):
    responses.get(COMMITS_URL, status=status)

    session.get(COMMITS_URL)
    second = session.get(COMMITS_URL)

    assert second.from_cache is False


@responses.activate
def test_token_is_not_stored_in_the_cache(tmp_path):
    responses.get(COMMITS_URL, json=[])
    session = build_session(tmp_path, expire_after=3600)

    session.get(COMMITS_URL, headers={"Authorization": "Bearer secret-token",
                                      "X-Probe": "stored-header"})
    session.close()

    stored = (tmp_path / CACHE_FILE_NAME).read_bytes()
    assert b"stored-header" in stored  # headers are readable in the file...
    assert b"secret-token" not in stored  # ...but the token is not there


@responses.activate
def test_expired_response_is_fetched_again(tmp_path):
    responses.get(COMMITS_URL, json=[])
    session = build_session(tmp_path, expire_after=0)

    session.get(COMMITS_URL)
    second = session.get(COMMITS_URL)
    session.close()

    assert second.from_cache is False
    assert len(responses.calls) == 2


@responses.activate
def test_cache_is_stored_in_the_given_directory_which_is_created(tmp_path):
    cache_dir = tmp_path / "nested" / "cache"
    responses.get(COMMITS_URL, json=[])
    session = build_session(cache_dir, expire_after=3600)

    session.get(COMMITS_URL)
    session.close()

    assert (cache_dir / CACHE_FILE_NAME).is_file()


@responses.activate
def test_settings_default_to_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_COMMITS_CACHE_PATH", str(tmp_path))
    monkeypatch.setenv("GH_COMMITS_CACHE_TTL", "60")
    responses.get(COMMITS_URL, json=[])

    session = build_session()
    session.get(COMMITS_URL)
    session.close()

    assert (tmp_path / CACHE_FILE_NAME).is_file()
    assert session.settings.expire_after == 60


def test_session_retries_transient_failures(session):
    retry = session.get_adapter("https://api.github.com").max_retries

    assert retry.total == 3


def test_cache_dir_defaults_to_user_cache(monkeypatch):
    monkeypatch.delenv("GH_COMMITS_CACHE_PATH", raising=False)

    assert cache_dir_from_env() == Path.home() / ".cache" / "github-commits"


def test_cache_dir_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GH_COMMITS_CACHE_PATH", str(tmp_path))

    assert cache_dir_from_env() == tmp_path


@pytest.mark.parametrize("value", [None, ""])
def test_expire_after_defaults_to_one_hour(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("GH_COMMITS_CACHE_TTL", raising=False)
    else:
        monkeypatch.setenv("GH_COMMITS_CACHE_TTL", value)

    assert expire_after_from_env() == DEFAULT_EXPIRE_AFTER_SECONDS == 3600


@pytest.mark.parametrize("value, expected", [("0", 0), ("120", 120)])
def test_expire_after_from_environment(monkeypatch, value, expected):
    monkeypatch.setenv("GH_COMMITS_CACHE_TTL", value)

    assert expire_after_from_env() == expected


@pytest.mark.parametrize("value", ["soon", "1.5", "-1"])
def test_invalid_expire_after_raises(monkeypatch, value):
    monkeypatch.setenv("GH_COMMITS_CACHE_TTL", value)

    with pytest.raises(ValueError, match="GH_COMMITS_CACHE_TTL"):
        expire_after_from_env()
