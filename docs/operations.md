# RWI operations

## Configuration

Copy `.env.example` to `.env` and fill every blank locally. Do not paste or commit the
result. Deployment identifiers are required rather than embedded in source defaults.
Use a unique, randomly generated database password and keep the database URL consistent
with the database service settings.

`RWI_CURRENT_GAME_VERSION` selects the exact season/patch scope used for new Community
Builds index records and local retrieval; the default is `Y8S3 Red Horizon`.
`RWI_CURRENT_GAME_VERSION_STARTED_ON` sets the hard freshness boundary; the deployed
value is `2026-08-27`. Older material is historical only and cannot support current-game
stats, acquisition routes, system behavior, bugs, or fixes.

`RWI_OFFICIAL_SEARCH_DOMAINS` contains first-party domains. `RWI_OFFICIAL_SEARCH_URLS`
contains exact first-party pages hosted on otherwise multi-tenant domains; the default is
Ubisoft's linked Division 2 Known Issues Trello board. `RWI_COMMUNITY_SEARCH_DOMAINS`
controls curated discovery across Wikipedia, Division wikis, Reddit, Steam, and selected
Q&A/community forums. Adding a domain expands discovery but does not elevate community
content to first-party evidence. Do not replace the exact Trello URL with a domain-wide
trust rule.

Community-claim retrieval requires a meaningful query anchor in addition to fuzzy
similarity. If a local generation still reports insufficient evidence, ERIN escalates to
curated and then open web search. A current curated wiki can support a stable descriptive
fact; live mechanics, stats, and builds continue to require stronger corroboration.
The fallback prompt omits the insufficient local excerpt so a stale partial claim cannot
force current external evidence into an artificial conflict.
The provider may return source links either as inline annotations or under web-tool source
metadata. Both forms are extracted; a nonzero web-tool count with no retained citations is
therefore a useful signal that the search returned no usable source links.

`RWI_COMMUNITY_LOADOUT_INDEXING_ENABLED` controls whether new and edited public forum
starter posts are indexed. ERIN's server nickname is reconciled idempotently on each
Discord connection and does not change the application ID, credentials, or permissions.

`RWI_VIDEO_INSPECTION_ENABLED`, `RWI_VIDEO_MAX_DURATION_SECONDS`,
`RWI_VIDEO_MAX_BYTES`, and `RWI_VIDEO_SAMPLE_FRAMES` bound gameplay-video processing.
The container includes FFmpeg/FFprobe; changing `RWI_FFMPEG_BINARY` or
`RWI_FFPROBE_BINARY` is intended only for a controlled non-container deployment. Raw
recordings and sampled frames are temporary and must never be copied into logs, audits,
knowledge entries, backups, or source control.

`RWI_AUTONOMOUS_RESEARCH_ENABLED` controls the live update monitor.
`RWI_AUTONOMOUS_RESEARCH_INTERVAL_HOURS` sets lightweight check cadence, while
`RWI_AUTONOMOUS_FULL_SWEEP_HOURS` sets the maximum interval between cross-source sweeps.
The full interval cannot be shorter than the check interval. Maximum findings and strict
official auto-promotion are separately configurable. Autonomous calls cannot spend the
member reserve. Use `/rwi research-status` to inspect the checkpoint and
`/rwi research-now` to request a staff-authorized full sweep.

`RWI_ROTATION_UPDATES_ENABLED` controls the Rotation publisher.
`RWI_ROTATION_REFRESH_MINUTES` controls direct-feed refreshes and
`RWI_ROTATION_WEB_REFRESH_HOURS` bounds the more expensive corroborating web pass.
`RWI_ROTATION_ESCALATION_URL` and `RWI_ROTATION_CALENDAR_URL` must remain bounded HTTPS
JSON endpoints. Staff can inspect state with `/rwi rotations-status` or immediately
refresh all posts and force web research with `/rwi rotations-now`. Maintenance mode
stops both scheduled and manual rotation research.

ERIN also reconciles only the explicitly requested `#erin-patch-notes` channel on a
healthy Discord connection. The channel is readable but not writable by Agent and Rogue
Agent roles. This targeted operation does not reconcile other channels or the role
hierarchy.

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

## Release announcements

Production releases are declared in `src/rwi_bot/data/releases.py`. Add one immutable
`Release` record per authored update with a unique lowercase release ID, the next ERIN
Update number, a `Vmajor.minor.patch` version, release date, and one or more categorized
notes. Notes render in severity/significance order regardless of declaration order. The
initial public entry is **ERIN Update 1 — V0.1.0**. The package version follows the
latest authored private-alpha release. Maintenance releases advance the patch component chronologically
(`V0.1.1`, `V0.1.2`, and so on); authored milestones may advance the minor component.

After an image containing a new release is deployed, startup automatically creates or
repairs `#erin-patch-notes` and publishes every entry not yet recorded in that channel.
Rebuilding or restarting the same image does not repost it. If a Git update is built and
deployed without an authored record, ERIN detects the changed deployment fingerprint,
increments the last patch version, and posts a conservative categorized summary of the
affected application components. Add an authored manifest whenever exact member-facing
detail is available; the fallback exists so a deployed change is never invisible.

No release publication occurs during durable maintenance mode. A successful
`/rwi resume` schedules pending announcements. If the Alliance Hub category or required
community roles do not exist, ERIN logs the failure and leaves the rest of the server
untouched.

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

### Community claim review

When a member makes a substantial factual correction or addition after an ERIN answer in
a public `ask-rwi` thread, ERIN stores it as pending and posts a private review card in
`#technician-lab`. DMs, low-substance comments, ordinary questions, and members with
shared learning disabled are excluded. A warning is added when the submission itself
mentions a possible bug, glitch, or exploit.

Technicians, Division Commanders, and the configured owner can use the persistent
**Accurate**, **Qualify**, **Incorrect**, **Bug**, or **Exploit** buttons. Qualify and all
negative decisions open a required explanation field. Reviewers can instead reply to the
card with `Yes`, `Yes, but <limitation>`, or `No, <reason>`; `No` without an explanation
does not resolve the record. Mention `bug` or `exploit` in a negative reply to select the
corresponding prohibited state.

Accurate and qualified claims immediately become searchable only for their recorded game
version. The qualification is controlling context. Pending, incorrect, bug, and exploit
claims are never used in answers, and ERIN is instructed to recommend a legitimate
alternative rather than an unintended mechanic. All decisions are permission-checked,
single-resolution, and audited. Claim writes stop during maintenance mode.

If a contributor later disables shared learning, their pending claims are removed and
their identity is anonymized on already-reviewed claims. `/privacy export` includes their
claim records; confirmed reset applies the same deletion/anonymization boundary.

Use `/rwi seed-red-horizon` to preview the built-in current-season baseline sourced from
[Ubisoft's official Red Horizon launch notes](https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/4mrYiFPIyKpzpoqshDQk80/the-division-2-red-horizon).
The private preview lists the total, new, and already-existing identities and requires
user-bound confirmation. The import creates active revision-1 entries with immutable
official source snapshots; it never overwrites an existing subject/claim/context
identity. Service startup performs the same create-only, idempotent import automatically;
the command remains available for private inspection and manual recovery. Re-running it is
safe and imports only identities still missing.

The packaged baseline contains the final official Brand/Gear updates and the complete
Red Horizon Skill table as 43 PvE plus 43 PvP records. The Skill PDF extraction script is
`scripts/extract_red_horizon_skills.py`; generated records retain their source pages and
`pdf_table_text` extraction method. Regeneration requires the bundled document Python
runtime with `pdfplumber`, and generated values must be reviewed against rendered source
pages before deployment. Community indexes, forums, Reddit, screenshots, OCR text, and
video transcripts are discovery or candidate material. Do not activate mutable current-
game claims from a single community host, and never let pre-August 27, 2026 material
verify a current Red Horizon mechanic.

The bundled `src/rwi_bot/data/div2hub_snapshot` directory is a low-trust research index,
not an automatic knowledge seed. `SNAPSHOT.json` pins the upstream commit, timestamp,
license, record count, and trust boundary; the upstream README, license, known gaps, and
game-text-error notes are preserved beside the CSV files. A matching row may improve
ERIN's external search query, but it cannot answer a question without the usual current
source evidence. When refreshing this snapshot, review its upstream diff, confirm the
commit is newer than the current-game boundary, update attribution and record counts,
run the catalog tests, and deploy it as a new ERIN release so cache signatures change.

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
candidates or community claims, persist positive cache feedback, or attach the requester
identity to new review tickets. Questions still have to be processed—including by the
configured external provider when required—to answer the member.

Normal answers contain no Sources section or explicit links. A member can reply with a
source-only request such as `sources?` or `where did you get that?` to receive the stored
citations for ERIN's immediately preceding answer without another OpenAI request. Simple
explicit feedback such as `thanks`, `that worked`, `that's wrong`, or `that's outdated`
is also handled locally and does not consume the member answer limit. Mixed feedback plus
a new question records the signal and continues through the normal answer path.

ERIN checks provider completion state before sending or caching an answer. A token-limit
cutoff receives one automatic concise retry. If the retry is also incomplete, the draft is
discarded and ERIN asks the member for current information. An `answer_retry` or
`web_answer_retry` usage operation records the combined cost of both attempts. If the
member says they do not know, the original question is then escalated to Technicians.

ERIN removes its internal evidence-confidence marker before sending. An unknown/low
assessment, or web support limited to one non-authoritative host after fallback search, is
not delivered as an answer: ERIN admits uncertainty and asks the member for clarification
or the correct answer. Substantive replies enter community review and stop the answer
cycle; they are not reprocessed as new questions. A member who cannot provide the answer
can explicitly defer to Technicians. The resulting alert contains the sanitized original
question, a human-readable failure explanation, whether web search ran, and the specific
verification requested instead of only internal event and target identifiers.

Members can update their own answer profile with explicit first-person statements such
as `I'm SHD 2500 and Expertise 20`, `I play PvP`, or `I prefer technical answers`.
Profile-only updates and `show my profile` are handled locally without consuming an
answer request. If a profile declaration also contains a question, ERIN writes the new
values first and answers using them. Supported values are character level 1–40, SHD
0–1,000,000, Red Horizon Expertise 0–30, PvE/PvP mode, maximum/current item-roll
assumptions, conditional-buff inclusion, and concise/standard/technical detail.
Profiles also support Xbox/PC/PlayStation, PvE/PvP/Both focus, gamertag, preferred
playstyle, and up to 20 explicit game-relevant notes. Natural notes cover experience,
main roles, likes, and dislikes; `Add to my profile: ...` stores another note and
`forget that ...` removes it. New members receive one private introduction after
membership screening. Sharing profile information is optional and does not affect access.
In DMs, `Start my personalization interview` (and equivalent onboarding/profile-interview
requests) starts a guided six-question flow. Members may skip any field or stop at any time.

Potential real-world personal data is never written as a profile update or sent into the
answer path. ERIN asks whether the withheld text was sensitive or game-related while
retaining only a redacted marker. A sensitive confirmation clears process-local memory
and removes matching legacy notes. A game-related confirmation requires the member to
resend only a clearly labeled game detail such as a gamertag.

Only self-reports are accepted; statements about another member cannot update a profile.
In a public thread, recent public context is author-labeled while the active assumptions
always come from the current message author's private profile. `/privacy status` displays
the member's saved answer profile alongside learning status. Export includes the stored
fields and reset restores their defaults. Profiles are keyed by Discord user ID in the
database, so they persist across threads, bot restarts, and current-member DMs. Normal
answers do not append a profile or assumptions footer; ERIN mentions a setting only when
it needs clarification, materially affects the recommendation, or the member asks.

`/privacy export` privately attaches a JSON export of the member profile, persisted
conversation summaries, feedback, indexed Community Builds starter posts, and contributed
community claims.
`/privacy reset` requires user-bound confirmation, then resets profile preferences,
deletes persisted conversation, feedback, Community Builds index state, and pending
claims; anonymizes reviewed claims plus review-ticket and API-usage associations; and
clears in-process conversation memory. The
learning preference is preserved. Neither reset nor learning opt-out deletes the original
Discord post; it removes ERIN's indexed copy. Security, moderation, and immutable audit
records are retained for integrity and are disclosed in both the confirmation and export.
Privacy controls fail closed during emergency maintenance mode with no data change.

Community indexing is limited to public starter posts in the configured
`community-builds` or `community-loadouts` forum. Replies and other channels are not
indexed. Edits refresh the sanitized local copy, message or thread deletion removes it,
and a bounded startup synchronization covers at most 100 active or archived threads.

## Scheduled operations

With automatic server bootstrap enabled, startup reconciles the mentionable `Raid &
Incursion Matchmaking` opt-in role and the member-readable, bot-writable
`#scheduled-operations` channel under MATCHMAKING. The channel denies member messages;
all interaction happens through persistent components. Its pinned alert panel lets a
member add or remove the notification role without a paid provider call.

Members can write requests such as `Set up a Broken Rain run in 2 days` in DMs,
`#ask-rwi`, or another guild channel. ERIN always asks for the organizer's role, then asks
for any missing supported activity, date, time, or timezone. Supported timezone labels
are ET/CT/MT/PT (including standard/daylight abbreviations) and UTC/GMT. Events must be at
least five minutes and no more than 180 days in the future. Drafts expire after 20 minutes
and `cancel` abandons them without writing an event.

The final post pings only the opt-in matchmaking role. Members choose a role to RSVP
Going, or use Going/Undecided, Maybe, and Withdraw controls. Going respects the operation
capacity; Maybe is the standby list. One hour before start, ERIN mentions every active
RSVP once and offers Confirm attendance or Withdraw. PostgreSQL stores UTC start times,
roster state, confirmation timestamps, and the Discord presentation pointers. Persistent
views are restored during startup, and completed operations age out of the active view
set six hours after start.

Explicit damage calculations should include a base value and labeled percentages, for
example: `Show me the damage math: base damage 100000, weapon damage 120%, TWD 25%, HSD
100%, CHD 150%, DTA 6%, DTOC 10%. The shot is a critical headshot against an armored
target out of cover.` ERIN validates the 60% CHC cap and shows each bucket, condition,
multiplier, and running result. Source links remain hidden until the member asks for them.

## Game rotations

On a healthy Discord connection, ERIN reconciles the member-readable, bot-writable
`ROTATIONS` category and five read-only channels: `#daily-targeted-loot`,
`#weekly-mission-rotations`, `#descent-rotation`, `#seasonal-rotations`, and
`#reset-timers`. Each channel contains one pinned ERIN post that is edited only when its
content changes.

The structured Escalation feed must contain an entry dated exactly for the current UTC
day; a future or stale entry is rejected. The calendar feed supplies dated seasonal
windows and the cyclic Descent rollover. Exact regional targeted-loot assignments,
Invasion and Legendary projects, the named Descent pool, Classified Assignment, and Dark
Zone state come through a budget-isolated curated web pass. Research output must be dated,
within its validity window, and backed by retained citations. Official claims require
official citations; community claims require current corroboration or an approved live
reference. Single unverified reports never publish.

A missing source produces a plain unconfirmed entry instead of a guess. A failed refresh
leaves existing Discord posts intact, persists a local diagnostic checkpoint, and retries
on the configured interval. The public posts omit source lists in keeping with ERIN's
normal response style; retained provenance remains available for operator inspection.

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
