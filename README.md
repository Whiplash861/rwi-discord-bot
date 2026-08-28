# RWI Discord Bot

The Redwing Initiative bot is a source-backed, conversational Discord assistant for
Tom Clancy's The Division 2. It combines a versioned community knowledge library,
deterministic game calculations, Technician governance, and tightly budgeted OpenAI
Responses API calls.

This repository is under active private-alpha development.

## Non-negotiable operating rules

- Discord and OpenAI credentials are environment variables and are never committed.
- The database is authoritative; Discord messages are presentation and editing surfaces.
- Generated text is never promoted to game truth without a source and provenance record.
- Numerical claims must come from structured data and deterministic calculations.
- Technician changes are versioned, confirmed, audited, and reversible.
- `/rwi halt` enters durable Do Not Disturb maintenance mode and blocks new paid calls.
- Normal answers are limited to DMs from current RWI members and `#ask-rwi`.
- Raw DMs, secrets, and unnecessary personal information are excluded from audit logs.

## Local quick start

1. Install Docker Desktop with WSL2 support.
2. Clone this repository to `C:\Projects\rwi-bot`.
3. Copy `.env.example` to `.env` and fill the values locally.
4. Generate a long random `RWI_DB_PASSWORD` and use it in both database settings.
5. Run `docker compose build`.
6. Run `docker compose run --rm bot alembic upgrade head`.
7. Run `docker compose up -d`.
8. Inspect startup with `docker compose logs -f bot`.

Do not paste secrets into Discord, ChatGPT, GitHub issues, screenshots, or logs.

## Development

```powershell
uv sync --extra dev
uv run ruff check .
uv run pytest
```

Architecture and operations documentation live under `docs/`.

