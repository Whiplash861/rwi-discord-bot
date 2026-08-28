# RWI operations

## Configuration

Copy `.env.example` to `.env` and fill every blank locally. Do not paste or commit the
result. Deployment identifiers are required rather than embedded in source defaults.
Use a unique, randomly generated database password and keep the database URL consistent
with the database service settings.

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
Disturb with `RWI Maintenance Mode`; offline presence remains reserved for a real process
or connectivity outage.

Use `/rwi status` to inspect the state. `/rwi resume` runs health checks and does not
replay work that accumulated before the halt. `/rwi resume force` is restricted to the
configured owner.

If the minimal Discord control listener is unavailable, stop the containers locally:

```powershell
docker compose stop bot
```

Do not use local container startup as a substitute for `/rwi resume` when the durable
halt file is active; the restarted bot will correctly remain halted.

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
