# Two images from one file:
#   runtime (default): the github-commits CLI as entrypoint
#   test:              the test suite with the dev dependencies
#
# Dependencies are installed before the source code is copied, so the
# dependency layer is reused from the cache as long as requirements*.txt
# do not change. requirements*.txt must match the lists in pyproject.toml.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GH_COMMITS_CACHE_PATH=/home/app/.cache/github-commits

# Non-root user. The cache directory exists in the image and belongs to that
# user, so a named volume mounted there inherits the right owner.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p "$GH_COMMITS_CACHE_PATH" \
    && chown -R app:app /home/app/.cache

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt


FROM base AS test

COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY --chown=app:app pyproject.toml README.md ./
COPY --chown=app:app src ./src
COPY --chown=app:app tests ./tests
RUN pip install --no-deps . \
    && chown app:app /app

USER app
CMD ["pytest", "--cov", "--cov-report=term-missing"]


FROM base AS runtime

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps . \
    && rm -rf /app/*

USER app
WORKDIR /home/app
ENTRYPOINT ["github-commits"]
CMD ["--help"]
