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
)
