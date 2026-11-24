"""Builds the cached HTTP session that GitHubClient uses.

Responses are stored in a local SQLite database with requests-cache. Only
successful (200) responses are cached, so errors and rate limits are never
reused. An expired response is revalidated with its ETag; GitHub answers a
matching ETag with 304 Not Modified, which does not count against the rate
limit. requests-cache leaves the Authorization header out of the cache key
and does not store it, so the token never ends up on disk.
"""

import os
from pathlib import Path
from requests_cache import CachedSession
from gh_commits.client import mount_retries

CACHE_DIR_VARIABLE = "GH_COMMITS_CACHE_PATH"
CACHE_TTL_VARIABLE = "GH_COMMITS_CACHE_TTL"
DEFAULT_CACHE_DIR = Path("~/.cache/gh-commits")
DEFAULT_EXPIRE_AFTER_SECONDS = 3600
CACHE_FILE_NAME = "http_cache.sqlite"


def cache_dir_from_env() -> Path:
    """Return the cache directory from GH_COMMITS_CACHE_PATH, or the default."""
    return Path(os.environ.get(CACHE_DIR_VARIABLE) or DEFAULT_CACHE_DIR).expanduser()


def expire_after_from_env() -> int:
    """Return the cache lifetime in seconds from GH_COMMITS_CACHE_TTL, or the default.

    Raises ValueError if the variable is not a non-negative whole number.
    """
    value = os.environ.get(CACHE_TTL_VARIABLE)
    if not value:
        return DEFAULT_EXPIRE_AFTER_SECONDS
    try:
        seconds = int(value)
    except ValueError as error:
        raise ValueError(
            f"{CACHE_TTL_VARIABLE} must be a whole number of seconds, got '{value}'."
        ) from error
    if seconds < 0:
        raise ValueError(f"{CACHE_TTL_VARIABLE} must not be negative, got '{value}'.")
    return seconds


def build_session(cache_dir: Path | None = None,
                  expire_after: int | None = None) -> CachedSession:
    """Build a cached session with retries for transient failures.

    The database is stored as `http_cache.sqlite` in `cache_dir`; the
    directory is created when needed. Settings that are not given are read
    from the environment (see cache_dir_from_env and expire_after_from_env).
    """
    if cache_dir is None:
        cache_dir = cache_dir_from_env()
    if expire_after is None:
        expire_after = expire_after_from_env()
    session = CachedSession(
        str(cache_dir / CACHE_FILE_NAME),
        backend="sqlite",
        expire_after=expire_after,
    )
    mount_retries(session)
    return session
