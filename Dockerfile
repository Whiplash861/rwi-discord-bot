FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system rwi \
    && useradd --system --gid rwi --create-home rwi

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY Dockerfile compose.yml ./release-inputs/
COPY scripts ./release-inputs/scripts

RUN python -m pip install --no-cache-dir .

RUN mkdir -p /data/runtime && chown -R rwi:rwi /data /app
USER rwi

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -m rwi_bot.preflight --healthcheck || exit 1

CMD ["python", "-m", "rwi_bot.main"]

