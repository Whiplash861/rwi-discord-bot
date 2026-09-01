# ERIN — RWI Discord Bot

ERIN (Enhanced Reconnaissance, Intelligence, and Navigation) is The Redwing Initiative's
source-backed, conversational Discord assistant for
Tom Clancy's The Division 2. It combines a versioned community knowledge library,
deterministic game calculations, Technician governance, and tightly budgeted OpenAI
Responses API calls.

The bundled baseline catalog target is **Y8S3 Red Horizon**. ERIN can search structured claim
content—not only item titles—and can locally reference privacy-sanitized starter posts
from the server's Community Builds forum before considering an OpenAI request. Community
loadouts are presented as player submissions. Red Horizon's August 27, 2026 launch is
the current-game freshness boundary: older material can provide history but cannot
support a claim about how the game works now. When local coverage is missing, curated
discovery includes Ubisoft, the exact Division 2 Known Issues Trello board linked by
Ubisoft, Wikipedia and Division wikis, Reddit, Steam, and selected Q&A/community forums.
Current videos and Y8S3 community reference indexes may assist discovery, but one video,
forum post, or mutable community database cannot establish current mechanics by itself.
Reviewed community-memory matches require a meaningful shared subject/mechanic term; an
irrelevant fuzzy match cannot suppress web search. Insufficient local context escalates to
web search before ERIN abstains. A current curated wiki may support a stable descriptive
fact, while changeable mechanics still require stronger corroboration.
The official Red Horizon baseline, including all 29 changed Brand Sets, nine changed Gear
Sets, and Ubisoft's complete 43-variant PvE/PvP Skill table, is imported idempotently at
startup so a deployed bot cannot silently run with an empty core catalog. Skill records
retain base stats, Skill Tier 1-6 values, Overcharge details, source pages, and their text-
table extraction method. Broad Skill-family questions must name every current variant in
a complete answer; otherwise ERIN asks which variant the member means.
The same baseline includes every intended Normal-mode encounter in Operation Dark Hours
and Operation Iron Horse, with ordered progression mechanics, wipe conditions, and
generalized assignments such as DPS, Future support/healer, hazard tank, control room,
generator, drone-killer, RPG, key-runner, and encounter caller. These records carry a
Red Horizon audit date and exclude bugs, bypasses, cheeses, and speedrun exploits. Current
Toxic, Balanced, Classic, Invaded, and Blackout Dark Zone rules are stored separately so
ERIN does not confuse an invasion state with normalization or apply one variant's build
assumptions to another.
ERIN also ships a pinned, attributed 2,037-record Y8S3 community research snapshot for
exact item, talent, attribute, Skill, mod, weapon, and specialization discovery. Those
rows improve web-search terminology but are deliberately excluded from verified knowledge:
current claims still need official support or independent corroboration before delivery.
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
After membership screening, ERIN sends one private, consent-forward introduction. Members
may optionally supply platforms, focus, gamertag, preferred playstyle, experience, main
roles, likes, dislikes, or any other game-relevant note. Natural profile additions and
removals persist across threads and DMs. Suspected real-world personal data is withheld
before persistence or model use; ERIN asks for clarification using only a redacted local
marker, and a sensitive confirmation clears that temporary conversation memory and any
matching legacy profile notes.
Members who prefer a guided setup can ask ERIN in DMs to start the personalization
interview; she then collects six optional profile categories one question at a time.

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
withheld instead of being guessed. ERIN first asks the member for clarification or a
current in-game answer that can enter moderated review. A Technician ticket is created
only when the member says they cannot supply the missing information. Ticket alerts show
the original question, the specific failure, prior checks, and the requested research.
Talent and mechanic explanations surface supported activation, deactivation, limitation,
and interaction details in the first breakdown rather than waiting for a follow-up.
DTOC and DTTOOC both resolve to Damage to Targets Out of Cover. Explicit weapon-damage
calculation requests use a deterministic sequence that displays every substitution and
running result across Weapon Damage, Total Weapon Damage, the shared active HSD/CHD
bucket, DTA or DTH, DTOC, team effects in their verified categories, and independent
amplifiers.

Members can attach one gameplay recording up to 30 seconds in a DM or `#ask-rwi` request.
ERIN verifies the real media stream and duration, samples ordered high-resolution frames,
and analyzes visible HUD, loadout, combat, and mechanic changes with timestamp context.
She labels inference, does not claim to hear audio, never stores the upload or filename,
and records only privacy-safe technical metadata after the temporary media is deleted.

ERIN also runs a budget-isolated game-update monitor every six hours and a full curated
research sweep at least daily. It checks Ubisoft and the official Known Issues Trello,
then surveys current creator videos, community references, Q&A forums, Reddit, and player
discussion for corroborative leads. A new active season requires retrieved official
evidence. Strict, dated, high-confidence official changes may enter active knowledge;
community, creator, forum, and player findings remain candidates for Technician review.
Verified season transitions update the answer freshness boundary and invalidate older
answer caches. Staff can inspect this state with `/rwi research-status` or request a full
sweep with `/rwi research-now`; maintenance mode stops all autonomous work.

ERIN maintains a read-only `ROTATIONS` category with current targeted loot,
Escalation requisitions and missions, weekly activities, Descent talent-pool timing,
seasonal events, Dark Zone intelligence, and reset timers. Structured Escalation and
calendar feeds update the reliable core; exact regional maps, weekly assignments, and
talent-pool names publish only when current dated web evidence clears a strict confidence
gate. Regional loot can publish as dated map images or a categorized location list with
separate mission, area, Classified Assignment, Raid, and off-map sections. Invasion,
Descent, and Dark Zone reports must be complete before they publish. The five posts are
edited in place rather than repeated, and Discord timestamps render in each member's
local time.

Members can ask ERIN in a DM, `#ask-rwi`, or another server channel to schedule Broken
Rain, Paradise Lost, Dark Hours, or Iron Horse. ERIN collects the organizer's role and
any missing date, time, or timezone, then publishes an RSVP roster in the read-only
`#scheduled-operations` channel. Members can opt into the Raid & Incursion Matchmaking
alert role, choose their operation role, join the standby list, or withdraw. Events and
RSVPs survive restarts, and ERIN asks active RSVPs to confirm attendance one hour before
the scheduled start.
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
- Rotation posts retain their last safe value when a refresh fails and never label stale
  or weakly sourced data as current.

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

Third-party data attribution is recorded in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

