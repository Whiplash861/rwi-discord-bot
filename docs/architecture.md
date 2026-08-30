# RWI architecture

RWI is organized around three trust domains that must not be merged:

1. **Verified knowledge** is server-wide, source-backed, versioned game truth.
2. **Adaptive answer cache** stores reusable answer text and the exact knowledge
   revisions, assumptions, citations, model, prompt version, freshness, and feedback
   state that support it.
3. **Private member state** contains individual preferences, inventory, saved builds,
   and conversation context. Private state is never copied into shared cache entries.

PostgreSQL is authoritative for versioned application data. Discord is an interaction
and review surface. The local runtime volume holds the emergency maintenance state so a
database outage cannot silently reactivate paid or automated work.

## Request path

A member request is accepted only from the configured guild's `ask-rwi` space or from a
DM whose sender is still a guild member. Each member/channel or member/thread pair has
an isolated in-process conversation session.

The answer path is:

1. Reject immediately when durable maintenance mode is active.
2. Normalize aliases and common language locally.
3. Look for a fresh, dependency-valid shared cache entry.
4. Search active verified knowledge.
5. Use deterministic code for values and build legality as coverage is added.
6. Reserve budget before an external request can start.
7. Use OpenAI without web search when verified context is sufficient.
8. Use source-backed web fallback only when local coverage is missing and web search is
   enabled.
9. Open a sanitized Technician ticket when no answer can be verified.

An answer produced from the web remains externally sourced. It is not promoted to
verified knowledge automatically.

Every knowledge change creates an immutable revision snapshot containing its content,
context, status, game version, confidence, actor, reason, and timestamp. Revising or
rolling back a record transactionally marks caches that depend on the former current
revision stale. Rollback never rewrites history; it copies the selected snapshot into a
new current revision.

## Emergency boundary

`MaintenanceManager` serializes a durable JSON state file using atomic replacement. A
corrupt or unreadable file fails closed. Work waiting for an OpenAI concurrency slot is
rechecked after it reaches the slot and is rejected if a halt happened while it waited.
Budget reservations account for concurrent requests so several individually acceptable
requests cannot collectively cross the configured cap.

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
