# ERIN — RWI Discord Bot

ERIN (Enhanced Reconnaissance, Intelligence, and Navigation) is The Redwing Initiative's
source-backed, conversational Discord assistant for
Tom Clancy's The Division 2. It combines a versioned community knowledge library,
deterministic game calculations, Technician governance, and tightly budgeted OpenAI
Responses API calls.

The current catalog target is **Y8S3 Red Horizon**. ERIN can search structured claim
content—not only item titles—and can locally reference privacy-sanitized starter posts
from the server's Community Builds forum before considering an OpenAI request. Community
loadouts are presented as player submissions. Red Horizon's August 27, 2026 launch is
the current-game freshness boundary: older material can provide history but cannot
support a claim about how the game works now. When local coverage is missing, curated
discovery includes Ubisoft, the exact Division 2 Known Issues Trello board linked by
Ubisoft, Wikipedia and Division wikis, Reddit, Steam, and selected Q&A/community forums.
Normal answers keep citations out of the message; a member can ask for the sources from
ERIN's immediately preceding answer. Explicit natural follow-ups such as “thanks,” “that
worked,” “that's wrong,” or “that's outdated” replace rating buttons and are inferred
locally at high confidence.
Every deployed application revision is also represented in the community-readable,
read-only `#erin-patch-notes` index. Authored releases use severity-grouped notes;
deployment fingerprinting produces a categorized fallback when a release manifest was
not supplied.

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
- Members can opt out of shared answer learning and privately export or reset profile data.
- Release announcements are idempotent: reconnecting the same build never reposts it.

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
uv run ruff format --check .
uv run mypy src
uv run pytest
```

`rwi-preflight --healthcheck` validates configuration, the durable maintenance state,
and database connectivity without contacting Discord or OpenAI. It never prints secret
values.

See [`docs/architecture.md`](docs/architecture.md) for trust boundaries and
[`docs/operations.md`](docs/operations.md) for startup, health, backup, restore, and
maintenance procedures.

