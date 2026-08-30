# RWI operations

## Configuration

Copy `.env.example` to `.env` and fill every blank locally. Do not paste or commit the
result. Deployment identifiers are required rather than embedded in source defaults.
Use a unique, randomly generated database password and keep the database URL consistent
with the database service settings.

`RWI_CURRENT_GAME_VERSION` selects the exact season/patch scope used for new Community
Builds index records and local retrieval; the default is `Y8S3 Red Horizon`.
`RWI_COMMUNITY_LOADOUT_INDEXING_ENABLED` controls whether new and edited public forum
starter posts are indexed. ERIN's server nickname is reconciled idempotently on each
Discord connection and does not change the application ID, credentials, or permissions.

The bot requires Python 3.12. Docker provides that runtime even when the Windows host
uses another Python version.

Set `RWI_AUTO_BOOTSTRAP_SERVER=true` only for a new or deliberately reconciled server.
On its first successful Discord connection, the bot creates or updates the canonical
roles, categories, channels, permission overwrites, and onboarding panel without
deleting unrelated spaces. Later reconnects in the same process do not repeat the full
bootstrap.

The bot intentionally does not hold Administrator, View Audit Log, or Manage Nicknames.
Consequently, the initial bootstrap leaves those ungrantable staff permissions for the
server owner to finish manually:

1. Move Division Commander, Division Coordinator, and Technician above the managed RWI
   Bot role, preserving that order.
2. Enable Administrator on Division Commander.
3. Enable View Audit Log and Manage Nicknames on Division Coordinator.
4. Keep Agent, platform roles, and Rogue Agent below RWI Bot; Rogue Agent remains the
   lowest custom role.

Once a protected staff role is at or above the bot, later reconciliations leave its
permissions and display settings unchanged.

## Startup and health

Build and start the private stack:

```powershell
docker compose build
docker compose run --rm bot alembic upgrade head
docker compose up -d
docker compose ps
docker compose logs --tail 100 bot
```

The container healthcheck runs `python -m rwi_bot.preflight --healthcheck`. It validates
configuration without printing secret values, verifies that the durable maintenance
file is readable, and checks PostgreSQL with `SELECT 1`. An intentional maintenance halt
is healthy; an unreadable maintenance file is not.

For a local Python 3.12 development environment:

```powershell
uv sync --extra dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

## Maintenance mode

Use `/rwi halt` for cost, failure-loop, queue, source, or full-system emergencies. The
durable flag is written before normal bot work can continue. Presence changes to Do Not
Disturb with `ERIN Maintenance Mode`; offline presence remains reserved for a real process
or connectivity outage.

Use `/rwi status` to inspect the state. `/rwi resume` runs health checks and does not
replay work that accumulated before the halt. `/rwi resume force` is restricted to the
configured owner.

Status includes the OpenAI circuit-breaker state and recent failure count. Resume treats
an open breaker as a failed health check. After its cooldown it becomes half-open, which
allows resume and exactly one provider probe; a failed probe reopens a full cooldown.

If the minimal Discord control listener is unavailable, stop the containers locally:

```powershell
docker compose stop bot
```

Do not use local container startup as a substitute for `/rwi resume` when the durable
halt file is active; the restarted bot will correctly remain halted.

## Technician knowledge changes

Use `/rwi seed-red-horizon` to preview the built-in current-season baseline sourced from
[Ubisoft's official Red Horizon launch notes](https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/4mrYiFPIyKpzpoqshDQk80/the-division-2-red-horizon).
The private preview lists the total, new, and already-existing identities and requires
user-bound confirmation. The import creates active revision-1 entries with immutable
official source snapshots; it never overwrites an existing subject/claim/context
identity. Re-running it is safe and imports only identities still missing.

Exact Technicians, Division Commanders, and the configured owner can inspect an entry
with `/rwi knowledge-history`. Create the first source-backed revision with
`/rwi knowledge-create`. It requires a subject, stable `entity_type` and `claim_key`,
object-valued content and context JSON, a reason, and a JSON array of one to eight source
objects. Each source object requires `url`, `title`, `source_type`, and `trust_score`;
optional fields are `publisher`, `content_hash`, `supports_claim`, and `note`. URLs must
use HTTPS, cannot contain credentials or recognizable secret query parameters, and must
be unique in the proposal. Valid source types are `official`, `reproducible_test`,
`technician`, `community`, and `unverified`. An active entry must have at least one
supporting source.

The creation proposal privately shows the complete identity, status, content/context,
and source evidence. Confirmation atomically creates the entry, source links, and
immutable revision-1 source snapshot. A duplicate subject/claim/context identity or a
conflicting description of an already-known source URL is rejected instead of silently
overwriting data. Source URLs containing access tokens or other credentials must never
be submitted.

Use `/rwi knowledge-revise` with the entry UUID, a full
replacement `content_json` object, and a reason. Optional `context_json`, status, game
version, and confidence fields replace their current values; omitted fields are
preserved. Use `clear_game_version:true` to remove version scope explicitly.

The bot responds privately with a field-level proposal. Only the initiating user can
confirm it. A confirmed revision takes effect immediately, snapshots the currently
linked source evidence, invalidates answer caches that depend on the former revision,
and records the actor, reason, diff, and resulting revision in the audit trail. If the
entry changes while the proposal is open, the write is rejected and the command must be
run again.

`/rwi knowledge-rollback` accepts an entry UUID, historical revision number, and reason.
Rollback copies that immutable snapshot—including its source-evidence snapshot—into a
new revision; it never rewrites or deletes history. Knowledge writes are disabled while
maintenance mode is active.

Use `/rwi review-queue` to inspect deduplicated unresolved and member-disputed answers.
The displayed question is privacy-sanitized and never includes the requester identifier.
`/rwi review-claim` moves an open ticket to investigating. After reproducing the issue
and creating or revising the supporting knowledge, use `/rwi review-resolve` with the
ticket UUID, resolving knowledge-entry UUID, and a non-private resolution note. The bot
shows the status/link diff and requires user-bound confirmation. Concurrent ticket
changes are rejected instead of overwritten. Claim and resolution actions are audited;
all queue writes stop during maintenance mode.

Use `/rwi knowledge-report` for the current completeness and verification-health
summary. Its `stale_days` option controls the active-record freshness threshold. The
report also identifies possible source conflicts, represented by entries that have both
supporting and opposing source links, plus open review work and quarantined caches.

`/rwi cache-status` shows cache metadata and feedback without revealing answer text.
When a shared answer is suspect, `/rwi cache-quarantine` shows a state diff and requires
user-bound confirmation. Quarantine takes effect immediately, is conflict-safe and
audited, and does not change any knowledge entry. Cache writes are disabled during
maintenance mode.

## Member privacy controls

Members use `/privacy status` to inspect whether future interactions may contribute to
shared answer learning and `/privacy learning` to change that reversible preference.
Opted-out interactions may use existing cache entries but do not create shared cache
candidates, expose feedback controls, or attach the requester identity to new review
tickets. Questions still have to be processed—including by the configured external
provider when required—to answer the member.

`/privacy export` privately attaches a JSON export of the member profile, persisted
conversation summaries, feedback, and indexed Community Builds starter posts.
`/privacy reset` requires user-bound confirmation, then resets profile preferences,
deletes persisted conversation, feedback, and Community Builds index state, anonymizes
review-ticket and API-usage associations, and clears in-process conversation memory. The
learning preference is preserved. Neither reset nor learning opt-out deletes the original
Discord post; it removes ERIN's indexed copy. Security, moderation, and immutable audit
records are retained for integrity and are disclosed in both the confirmation and export.
Privacy controls fail closed during emergency maintenance mode with no data change.

Community indexing is limited to public starter posts in the configured
`community-builds` or `community-loadouts` forum. Replies and other channels are not
indexed. Edits refresh the sanitized local copy, message or thread deletion removes it,
and a bounded startup synchronization covers at most 100 active or archived threads.

## Backup

Database backups must be written outside the container and runtime volume. Create the
destination first, then run:

```powershell
docker compose exec -T db pg_dump -U rwi -d rwi -Fc > backups\rwi.dump
```

Protect the dump as production data: it may contain member identifiers, private
preferences, saved builds, and audit records. Keep at least one encrypted copy on media
separate from the bot host. The local maintenance JSON file should also be included in a
host backup of the Docker runtime volume.

## Restore drill

Test restores against a disposable database or isolated Compose project, never directly
over a running production database.

1. Stop the bot so it cannot write during restoration.
2. Create an empty target database with the required `vector`, `pg_trgm`, and `citext`
   extensions.
3. Restore the dump with `pg_restore --clean --if-exists --no-owner`.
4. Run `alembic upgrade head` against the restored database.
5. Run `rwi-preflight --healthcheck`.
6. Compare row counts for knowledge entries, revisions, sources, cache records, profiles,
   usage, and audit records.
7. Start the bot only after the drill passes and confirm maintenance state before resume.

Record the backup timestamp, restore target, migration revision, verification results,
and operator in the private operations log. A backup is not considered valid until a
restore drill has succeeded.

## Shutdown

Use `docker compose stop bot` for a graceful stop. The configured 30-second grace period
allows Discord and database resources to close. Use `docker compose down` only when the
database service may also stop; do not add `--volumes` unless permanent data removal is
explicitly intended and separately approved.
