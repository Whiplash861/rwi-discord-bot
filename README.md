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
Reviewed community-memory matches require a meaningful shared subject/mechanic term; an
irrelevant fuzzy match cannot suppress web search. Insufficient local context escalates to
web search before ERIN abstains. A current curated wiki may support a stable descriptive
fact, while changeable mechanics still require stronger corroboration.
The official Red Horizon baseline, including all 29 changed Brand Sets, is imported
idempotently at startup so a deployed bot cannot silently run with an empty core catalog.
Normal answers keep citations out of the message; a member can ask for the sources from
ERIN's immediately preceding answer. Explicit natural follow-ups such as “thanks,” “that
worked,” “that's wrong,” or “that's outdated” replace rating buttons and are inferred
locally at high confidence. Members can also explicitly tell ERIN their level, SHD,
Expertise, preferred mode, roll/buff assumptions, and answer-detail preference. Those
private settings persist per Discord user and drive that member's later answers. Public
thread context labels each author, so multiple agents can participate without one
member's profile being applied to another. The same database-backed profile follows a
current server member across public threads, process restarts, and DMs. ERIN uses it
silently instead of appending assumptions to every answer.

Substantial factual corrections in public ERIN conversations can enter a moderated
community-memory queue. ERIN archives the claim for experienced-member review in
`#technician-lab`; only verified or explicitly qualified Red Horizon claims become
searchable. Incorrect claims and techniques classified as bugs or exploits are retained
as review outcomes but excluded from recommendations. Build creation and content-fit
reviews include tiered Major, Situational, and Minor pros and cons.
Provider responses are generated completely before Discord delivery. If an answer reaches
its output limit, ERIN automatically regenerates a concise complete version once; a draft
that remains incomplete is neither sent nor cached.
Every generated answer also carries a hidden evidence assessment. ERIN can respectfully
correct a member when current evidence is strong, while low-confidence answers are
withheld and opened as Technician tickets instead of being guessed.
Every deployed application revision is also represented in the community-readable,
read-only `#erin-patch-notes` index. Authored releases use severity-grouped notes;
deployment fingerprinting produces a categorized fallback when a release manifest was
not supplied.

This repository is under active private-alpha development.

## Non-negotiable operating rules

- Discord and OpenAI credentials are environment variables and are never committed.
- The database is authoritative; Discord messages are presentation and editing surfaces.
- Generated text is never promoted to game truth without a source and provenance record.
- Raw member claims are never reusable until an authorized experienced member reviews them.
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

