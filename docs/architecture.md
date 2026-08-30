# RWI architecture

ERIN is organized around four trust domains that must not be merged:

1. **Verified knowledge** is server-wide, source-backed, versioned game truth.
2. **Community loadouts** are public player submissions indexed locally for retrieval.
   They are useful examples, not verified claims, and remain visibly labeled as such.
3. **Adaptive answer cache** stores reusable answer text and the exact knowledge
   revisions, assumptions, citations, model, prompt version, freshness, and inferred feedback
   state that support it.
4. **Private member state** contains individual answer assumptions, preferences,
   inventory, saved builds, and DM conversation context. Private state is never copied
   into another member's request or into shared cache entries.

Members control this boundary with `/privacy`. Learning opt-out is checked before each
answer: opted-out interactions can consume existing verified/shared answers but cannot
create shared cache candidates, persist positive cache feedback, or attach the requester identity
to new review tickets. It does not prevent the member's current question from being
processed to answer them.

Private export includes the member's profile, persisted conversation summaries,
feedback, and any indexed Community Builds starter posts they authored. Confirmed reset
clears those records and indexed copies, anonymizes review-ticket and usage associations,
and clears in-process conversation memory while preserving the learning preference. It
does not delete the original Discord forum post. Security, moderation, and immutable
audit records remain retained and are identified as such before reset.

PostgreSQL is authoritative for versioned application data. Discord is an interaction
and review surface. The local runtime volume holds the emergency maintenance state so a
database outage cannot silently reactivate paid or automated work.

## Request path

A member request is accepted only from the configured guild's `ask-rwi` space or from a
DM whose sender is still a guild member. DM context remains isolated by member. Public
thread context is shared because the messages are already visible there, but every
member message and ERIN response is author-labeled. Only the current author's private
profile is loaded into an answer request.

The answer path is:

1. Recognize explicit first-person profile updates and profile queries locally. Profile-
   only messages never call OpenAI or web search.
2. Load the current author's saved answer assumptions and detail tier. Reject immediately
   when durable maintenance mode blocks a normal answer.
3. Normalize aliases and common language locally.
4. For build advice, search the current-version Community Builds index and return a
   clearly labeled local match with links to the original posts when one is relevant.
5. Look for a fresh, dependency-valid shared cache entry whose signature includes the
   current author's assumptions.
6. Search active verified knowledge across subject, identity, structured content,
   context, and game-version text.
7. Use deterministic code for values and build legality as coverage is added.
8. Reserve budget before an external request can start.
9. Use OpenAI without web search when verified context is sufficient.
10. Use curated web fallback only when local coverage is missing and web search is enabled.
   The target set combines current Ubisoft material, the exact official Division 2 Known
   Issues Trello board, Wikipedia and Division wikis, Reddit, Steam, and selected Q&A and
   community forums. Community pages remain corroborative rather than first-party truth.
11. Open a sanitized Technician ticket when no answer can be verified.

Profile writes require explicit self-reference such as `I'm SHD 2500`, `my Expertise is
20`, or `I play PvP`. A statement about another member never updates either profile.
Profile-only acknowledgements and `show my profile` queries are deterministic local
responses. The current member can review the same values privately with `/privacy status`,
export them, or return them to defaults with the confirmed privacy reset.

All current-game paths share the `Y8S3 Red Horizon` version in their cache signature.
Local knowledge and Community Builds retrieval are constrained to that version, and the
August 27, 2026 launch date is passed to the answer model as a hard freshness boundary.
Older material may explain history but cannot support present-day stats, acquisition
routes, system behavior, bugs, or fixes.

Normal Discord answers omit explicit citations and source links. Citations remain attached
to the in-process conversation turn, and a source-only follow-up returns that stored list
without another provider request. Explicit feedback-only follow-ups are also handled
locally. High-confidence helpful signals update reusable answers; explicit incorrect or
outdated signals open or increment a review ticket and count against a reusable answer
when applicable. Signals are deduplicated per answer, negative cues take precedence over
mixed politeness, and ambiguous questions such as “could this be outdated?” are not scored.

The built-in current-season baseline is scoped to `Y8S3 Red Horizon` and uses
[Ubisoft's official launch notes](https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/4mrYiFPIyKpzpoqshDQk80/the-division-2-red-horizon).
It is a governed create-only import: it does not overwrite an entry with the same
subject, claim key, and context. This keeps launch values distinct from earlier PTS
values and preserves technician-authored revisions.

The Community Builds index accepts only non-bot starter posts in the configured guild's
public `community-builds` or `community-loadouts` forum. Replies, DMs, other channels,
and private or unrelated spaces are excluded. Content is sanitized before persistence;
edits update the index, deletion removes the indexed copy, and startup synchronization
is bounded to 100 active or archived threads. Learning opt-out removes the author's
indexed submissions and prevents re-indexing while the preference remains enabled.

## Release index

`#erin-patch-notes` is a community-readable text channel under Alliance Hub. Agent and
Rogue Agent overwrites explicitly deny sending messages, reactions, and thread creation;
ERIN retains the send and history permissions needed to maintain the index. Discord
server administrators can still moderate the channel because Administrator bypasses
channel overwrites.

Each authored release has a stable release ID, monotonically increasing ERIN Update
number, `Vmajor.minor.patch` version, date, and notes classified as Critical, Privacy &
Safety, High Impact, New Features, Improvements, Fixes, or Reliability & Maintenance.
The publisher reconciles only this explicitly requested channel; it does not run the
full server blueprint or change role hierarchy.

At startup ERIN fingerprints packaged application source, migrations, configuration,
container definitions, and deployment scripts. Pending authored releases are published
first. If the fingerprint changed without a new authored manifest, ERIN increments the
patch version and emits a conservative component-level fallback rather than silently
omitting the deployment. The fingerprint contains hashes and file labels, never source
content or credentials.

Publication is idempotent across reconnects and process restarts. A stable marker in the
Discord embed and an immutable audit event identify each release and destination channel;
a message sent immediately before a process interruption can therefore be recovered
without duplication. Durable maintenance mode suppresses channel creation and publishing;
a successful `/rwi resume` schedules all pending notes.

The deterministic build core keeps PvE and PvP stat variants explicit, excludes
conditional buffs unless requested, enforces data-driven activation and uniqueness
requirements, distinguishes gear and weapon Exotic limits, and records the default SHD
1000 / Expertise 0 assumptions. Exhaustive searches return both evaluated and total
combination counts. An impossible result is considered proven only when every legal
combination was evaluated; capped searches are labeled incomplete instead.

An answer produced from the web remains externally sourced. It is not promoted to
verified knowledge automatically.

Every knowledge change creates an immutable revision snapshot containing its content,
context, status, game version, confidence, linked-source evidence, actor, reason, and
timestamp. Revising or rolling back a record transactionally marks caches that depend
on the former current revision stale. Rollback never rewrites history; it copies the
selected snapshot into a new current revision.

Technician changes use typed `/rwi knowledge-create`, `/rwi knowledge-revise`,
`/rwi knowledge-rollback`, and `/rwi seed-red-horizon` controls. Creation requires typed
HTTPS source evidence and
atomically writes the entry, source links, and immutable initial snapshot. It rejects
duplicate knowledge identities, conflicting metadata for a known source URL, credential-
bearing URLs, and active claims without supporting evidence. The bot parses structured
JSON locally, checks the exact authorized staff roles, displays a deterministic proposal
or field-level diff, and binds confirmation to the user who opened it. A revision proposal
records its expected current revision; a concurrent change causes a conflict instead of
silently overwriting newer knowledge. Confirmed changes take effect immediately and write
a separate audit event containing the source summary or diff.

Unanswered questions and member-reported incorrect answers enter one deduplicated
Technician review queue. Before persistence, the queue text redacts Discord identifiers,
mentions, email addresses, IP addresses, phone numbers, and links; requester identifiers
are never shown in queue output. Claim and resolution transitions are typed, permission
checked, and audited. Resolution requires confirmation and a link to an existing
knowledge entry, and rejects stale confirmations if another Technician changed the
ticket first.

`/rwi knowledge-report` is a read-only integrity surface over authoritative database
state. It reports lifecycle counts, active records missing sources or game-version
scope, low-confidence and stale verification, mixed supporting/opposing source links,
open review work, and quarantined answer caches. `/rwi cache-quarantine` is a separate,
confirmed typed action: it stops a suspect shared answer from being served and records
the state transition without altering verified knowledge.

## Emergency boundary

`MaintenanceManager` serializes a durable JSON state file using atomic replacement. A
corrupt or unreadable file fails closed. Work waiting for an OpenAI concurrency slot is
rechecked after it reaches the slot and is rejected if a halt happened while it waited.
Budget reservations account for concurrent requests so several individually acceptable
requests cannot collectively cross the configured cap.

The OpenAI failure breaker uses a sliding failure window and a cooldown. Once cooldown
expires, exactly one leased half-open probe may run; all other provider work remains
blocked. A failed probe starts a new full cooldown, a successful probe closes the
breaker, and cancellation or a maintenance/budget rejection releases only that probe's
lease. This prevents both half-open request herds and a permanently stuck probe.

An already-started provider request may finish and be charged. No queued provider call
is allowed to begin after halt activation. Resume checks cannot overwrite a newer halt
that arrives while those checks are running.

## Discord authority

- Division Commanders, the configured owner, and members with the exact Technician role
  may halt, inspect, or resume maintenance mode.
- Only the configured owner may force-resume through failed health checks.
- Server bootstrap is limited to Division Commanders and the configured owner.
- An unrelated role with Discord Administrator permission is not treated as an RWI
  Commander.
- Technicians receive no moderation authority from the bot.

## Spam moderation

Spam detection is local and keeps only short-lived SHA-256 fingerprints, timestamps,
and attachment counts; message text is not written to discipline or audit records. A
first incident is deleted and warned, a later incident is temporarily timed out, and
continued or severe spam is kicked. The bot never automatically bans a member.

The configured owner, Discord server owner, Division Commanders, Division Coordinators,
Technicians, and members at or above the bot's highest role are excluded from automated
actions. Detection stops completely during durable maintenance mode. Conversation-space
messages pass through this check before any answer or paid provider request can begin.

Persistent platform-role buttons are bound to the configured RWI guild, toggle Xbox,
PC, and PS independently, reply ephemerally, and stop during maintenance. Rogue Agent
members cannot use the selector to bypass restrictions. These local Discord operations
never invoke OpenAI.

Live server reconciliation is a deliberate administrative action and is never run as
part of local tests or startup unless explicitly enabled.
