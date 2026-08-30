from __future__ import annotations

from datetime import date

from rwi_bot.services.releases import Release, ReleaseNote, ReleaseSection

RELEASES: tuple[Release, ...] = (
    Release(
        release_id="erin-update-1",
        update_number=1,
        version="V0.1.0",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Renamed the server assistant to ERIN: Enhanced Reconnaissance, "
                "Intelligence, and Navigation.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added structured Y8S3 Red Horizon knowledge search across item names, "
                "stats, context, and game-version data.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added local Community Builds indexing so ERIN can reference relevant "
                "player loadouts without an OpenAI request.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added the read-only #erin-patch-notes release index with automatic, "
                "once-per-deployment publishing.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Community loadout indexing now follows member learning opt-out, export, "
                "edit, and deletion controls.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Added release fingerprints and categorized fallback notes so unlisted "
                "deployed changes still receive an update entry.",
            ),
        ),
        legacy_release_ids=("erin-update-1-v1.22.333",),
    ),
    Release(
        release_id="erin-update-2",
        update_number=2,
        version="V0.1.1",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Made Y8S3 Red Horizon the current-game freshness boundary so older "
                "material cannot support present-day game claims.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Expanded ERIN's curated discovery across Ubisoft, the official Division 2 "
                "Known Issues Trello board, Wikipedia, Division wikis, Reddit, Steam, and "
                "selected Q&A and community forums.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Removed Sources sections and inline links from normal answers; members can "
                "ask for the previous answer's stored sources whenever they want them.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Removed answer-rating buttons and added high-confidence recognition of "
                "explicit helpful, incorrect, and outdated follow-up messages.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Feedback-only replies and source requests are handled locally without a new "
                "OpenAI request, and repeated feedback is deduplicated.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Kept community search-result provenance internal and limited first-party "
                "Trello trust to the exact board linked by Ubisoft.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-3",
        update_number=3,
        version="V0.1.2",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added durable per-member answer profiles so each message uses its author's "
                "saved level, SHD, Expertise, mode, roll, buff, and detail preferences.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN now recognizes explicit first-person profile updates and profile "
                "queries locally without an OpenAI or web request.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Public thread context now labels each member and ERIN response by author, "
                "allowing multiple agents to converse without exchanging profiles.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Only self-reported values update a profile; third-party statements are "
                "ignored, private profiles stay isolated, and saved values remain covered "
                "by privacy export and reset.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Fixed answer requests and assumption footers always falling back to SHD "
                "1000, Expertise 0, Level 40, PvE, and maximum rolls.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-4",
        update_number=4,
        version="V0.1.3",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added moderated community memory: substantial public corrections enter "
                "a pending Red Horizon review queue before ERIN can reuse them.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added persistent Accurate, Qualify, Incorrect, Bug, and Exploit controls "
                "in the Technician Lab, plus equivalent plain-language reply reviews.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Build creation and content-fit evaluations now include tiered Major, "
                "Situational, and Minor pros and cons.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Removed automatic assumptions footers; ERIN now uses saved profile values "
                "silently unless they clarify or materially affect an answer.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Excluded DMs and opted-out members from community-claim capture, added "
                "claims to privacy export/reset, and prohibited incorrect, bug, and exploit "
                "records from answer retrieval.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Locked profile lookup to the member's database-backed Discord identity so "
                "the same settings persist across threads, restarts, and eligible DMs.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Added durable claim review states, current-season filtering, audited "
                "single-resolution decisions, and stale-cache avoidance for reviewed claims.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-5",
        update_number=5,
        version="V0.1.4",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Moved community-claim capture behind ERIN's member fair-use limiter so "
                "repeated submissions cannot bypass conversation throttling or flood the "
                "private review channel.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Revalidated the moderated learning pipeline, persistent profiles, and "
                "footer-free answer path after deployment hardening.",
            ),
        ),
    ),
)
