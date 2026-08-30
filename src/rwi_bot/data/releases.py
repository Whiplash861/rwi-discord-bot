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
    Release(
        release_id="erin-update-6",
        update_number=6,
        version="V0.1.5",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "ERIN now challenges incorrect member premises when strong current "
                "evidence supports the correction, instead of agreeing for helpfulness.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Fixed answers stopping mid-sentence or mid-Markdown when the language "
                "provider reached ERIN's output-token ceiling.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Raised normal and complex response envelopes and added one automatic "
                "concise regeneration when a provider response reports a token-limit cutoff.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Incomplete drafts that survive the retry are now discarded instead of "
                "being sent or cached, and a Technician ticket is opened for review.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Answers without authoritative or independently corroborated current "
                "evidence are now withheld and sent to the Technician review queue rather "
                "than filled with a plausible guess.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Limited tiered pros and cons to actual build creation, build review, and "
                "content-fit requests so narrow factual answers remain focused.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-7",
        update_number=7,
        version="V0.1.6",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "Fixed partial or unrelated reviewed community claims suppressing internet "
                "search for questions such as current brand-set bonuses.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Community-memory retrieval now requires a meaningful shared subject or "
                "mechanic term in addition to fuzzy similarity.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "An insufficient local answer now escalates through curated and open web "
                "search instead of immediately opening an unanswered ticket.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Current curated wiki references may support stable descriptive facts, "
                "while changeable mechanics still require stronger corroboration.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-8",
        update_number=8,
        version="V0.1.7",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "Fixed valid web answers being rejected when the provider returned source "
                "links in web-tool metadata instead of inline citation annotations.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Web-search usage is now preserved on abstained responses, making search "
                "execution distinguishable from a local-only unanswered result.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-9",
        update_number=9,
        version="V0.1.8",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "Fixed incomplete or conflicting local context carrying into web fallback "
                "and causing current externally supported answers to be rejected.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "After local evidence proves insufficient, curated and open searches now "
                "perform an independent current-game verification of the original question.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-10",
        update_number=10,
        version="V0.1.9",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Imported Ubisoft's final Red Horizon bonuses for all 29 changed Brand "
                "Sets as source-backed verified knowledge.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Current verified Brand values now override conflicting older community "
                "notes and pre-season search results.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "The built-in Red Horizon baseline now imports idempotently during startup, "
                "preventing an empty production knowledge database after deployment.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-11",
        update_number=11,
        version="V0.1.10",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Unresolved answers now ask the member for clarification or current in-game "
                "information before creating a Technician ticket.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "A member can say they do not know the answer to escalate the original "
                "question, while substantive replies enter experienced-member review.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Archived member corrections now end the answer cycle instead of being "
                "misread as another question and spawning additional tickets.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Technician alerts now show the original question, the specific failure, "
                "checks already attempted, and the verification work requested.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Talent explanations now surface supported activation, deactivation, "
                "limitation, and interaction details in the initial breakdown.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "The natural question 'What do you know about me?' now opens the member's "
                "saved ERIN profile locally instead of entering the answer queue.",
            ),
        ),
    ),
)
