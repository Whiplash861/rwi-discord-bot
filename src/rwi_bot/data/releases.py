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
    Release(
        release_id="erin-update-12",
        update_number=12,
        version="V0.1.11",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Imported Ubisoft's final Red Horizon Skill tables for all 43 variants "
                "in both PvE and PvP, including base stats, Skill Tiers 1-6, and Overcharge.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "A 15-domain Division 2 research syllabus now guides local retrieval and "
                "web research across equipment, talents, activities, costs, lore, enemies, "
                "and encounter mechanics.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Broad Skill questions now require complete coverage of every current "
                "variant or a focused clarification instead of silently answering for one.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "The Discord account's global username now reconciles to ERIN so direct "
                "messages no longer display the former RWI Bot Dev identity.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Current video sources and Y8S3 community reference indexes can assist "
                "discovery, while mutable claims still require official or independent "
                "corroboration before ERIN treats them as reliable.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Expanded the built-in Red Horizon baseline with nine updated Gear Sets "
                "and current seasonal, PvP, Dark Zone, and Classified Assignment systems.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-13",
        update_number=13,
        version="V0.1.12",
        released_on=date(2026, 8, 30),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added a pinned local Y8S3 research index with 2,037 structured equipment, "
                "talent, attribute, Skill, weapon, mod, and specialization records.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN now uses exact local item and talent matches to improve web-research "
                "terms before answering unfamiliar Division 2 questions.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "The community snapshot is explicitly discovery-only and cannot bypass "
                "Red Horizon freshness, source corroboration, or confidence checks.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Pinned the reference snapshot to an attributed CC-BY-4.0 commit and retained "
                "its known-gap and measured-game-text documentation for review.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-14",
        update_number=14,
        version="V0.1.13",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added Red Horizon-audited progression mechanics and generalized role "
                "assignments for every Dark Hours and Iron Horse raid encounter.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added current Toxic, Balanced, Classic, Invaded, and Blackout Dark Zone "
                "rules with variant-specific build principles and warnings.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN now privately introduces herself after a member joins and offers an "
                "optional personalization interview for builds and advice.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Member profiles now support platform, PvE/PvP focus, gamertag, preferred "
                "playstyle, experience, main roles, likes, dislikes, and open-ended notes.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Possible real-world personal information is withheld instead of saved or "
                "sent to the answer model; ERIN asks the member to clarify and can scrub "
                "matching legacy notes.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Profile notes can be amended or forgotten naturally and remain available "
                "to the same member across server threads, restarts, and direct messages.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-15",
        update_number=15,
        version="V0.1.14",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "DM requests for the new-member personalization interview now enter the "
                "profile workflow instead of being treated as unanswered game questions.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added a guided six-question profile interview covering platform, focus, "
                "progression, gamertag, playstyle, and open-ended game preferences.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Every interview field is optional, supports skip or stop, and uses the "
                "same personal-information withholding and clarification safeguards.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-16",
        update_number=16,
        version="V0.1.15",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added durable Raid and Incursion scheduling with guided organizer-role, "
                "date, time, and timezone collection from member DMs or server channels.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added a read-only scheduled-operations channel, opt-in matchmaking alert "
                "role, role-aware RSVP roster, standby list, and attendance controls.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN now pings active RSVPs one hour before an operation and records their "
                "confirmation or withdrawal across process and desktop restarts.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Added DTOC as an alias for Damage to Targets Out of Cover and expanded "
                "weapon calculations into an ordered, fully shown bucket sequence.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Damage breakdowns now distinguish additive Weapon Damage, Total Weapon "
                "Damage, HSD/CHD, target layers, DTOC, team effects, and amplifiers.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Scheduling uses daylight-saving-aware timezones and PostgreSQL-backed "
                "events and RSVPs, with persistent Discord controls restored at startup.",
            ),
        ),
    ),
    Release(
        release_id="automatic-c72efd2ce168db74",
        update_number=17,
        version="V0.1.16",
        released_on=date(2026, 8, 31),
        automatic=True,
        notes=(
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Recorded the live scheduler startup refinement through ERIN's automatic "
                "deployment fingerprint and chronological patch-note fallback.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-18",
        update_number=18,
        version="V0.1.17",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "The scheduling feature now creates and reconciles its opt-in Raid & "
                "Incursion Matchmaking role even when full automatic server bootstrap is off.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Completed live migration, role, channel, pinned alert panel, persistent "
                "component, and container health verification for the scheduler rollout.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-19",
        update_number=19,
        version="V0.1.18",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added complete, ordered encounter guidance and role-specific build advice "
                "for Paradise Lost, Broken Rain, Operation Dark Hours, and Operation Iron Horse.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN now predicts canonical Incursion and Raid targets from boss-only names, "
                "aliases, shorthand, common misspellings, and varied question phrasing.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Questions about Lovebirds, Wright, Iris Steel, and the Meret Estate now route "
                "to the correct current encounter records instead of failing retrieval.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Encounter answers now lead with the objective and team setup, then present "
                "numbered mechanics, wipe conditions, callouts, and recommended builds.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Current Incursion guidance excludes immunity bypasses, one-shot shortcuts, "
                "melee phase skips, cheeses, bugs, and exploits.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Expanded the Red Horizon local knowledge seed to 183 versioned records and "
                "invalidated older answer-cache prompts for the new encounter format.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-20",
        update_number=20,
        version="V0.1.19",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added shared query intelligence that resolves likely names and syntax into "
                "multiple focused searches across ERIN's current local knowledge.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "ERIN now rejects high-scoring but unrelated local records instead of using "
                "them to avoid a required current-evidence web search.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Fixed the DM personalization interview's Ubisoft/gamertag label detection so "
                "already labeled answers are stored cleanly.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Expanded Division shorthand, typo handling, intent recognition, and mode, "
                "difficulty, role, platform, and group-size constraint extraction.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Comparisons, acquisitions, builds, and complete-scope requests now receive "
                "task-specific response plans and stricter completeness checks.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Expanded ERIN's knowledge curriculum for buildcraft, combat mathematics, "
                "Raids, Dark Zone rules, progression, and live-service status.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Raid and Incursion scheduling now understands more activity aliases, weekday "
                "dates, 24-hour time, noon or midnight, and specialist RSVP roles.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Added ranked multi-query retrieval, superseded-guide filtering, prompt v15, "
                "and broader regression coverage for ERIN's upgraded reasoning path.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-21",
        update_number=21,
        version="V0.1.20",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "Tightened canonical stat resolution after live verification so generic "
                "terms such as Armor cannot override a specific Armor Regeneration request.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Reference discovery now expands ERIN's Division aliases before matching, "
                "while generic catalog labels remain search hints instead of answer targets.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Added a regression for the 6% Armor Regen request and revalidated typo, "
                "intent, evidence-routing, and canonical-name behavior.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-22",
        update_number=22,
        version="V0.1.21",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "Restored natural acquisition wording such as how to get an item and where "
                "an item drops without misclassifying percentage-stat build targets.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Exact item and talent names now outrank higher-scoring fuzzy prefixes, "
                "preventing Vigil from displacing Vigilance in interaction questions.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Expanded typo discovery around natural phrases such as how a talent works "
                "and improved descriptive build-review intent detection.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Added query-matrix regressions for acquisition, stat goals, comparisons, "
                "talent interactions, encounter guides, and profile-aware build reviews.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-23",
        update_number=23,
        version="V0.1.22",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN can now visually inspect one user-supplied Division 2 gameplay video "
                "up to 30 seconds using ordered timestamped frames.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Gameplay recordings and extracted frames are temporary, filenames are not "
                "audited, audio is excluded, and raw media is deleted before the reply.",
            ),
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added guarded autonomous game-update research with official season detection, "
                "dynamic freshness boundaries, and automatic stale-cache invalidation.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Only dated, high-confidence official findings can auto-promote; creator, "
                "forum, Q&A, Reddit, and player findings remain review-gated candidates.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Staff can inspect autonomous research state or request a full cross-source "
                "sweep with the new research-status and research-now commands.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Added FFmpeg media verification, configurable video and research limits, "
                "budget-reserved autonomy, safe failure audits, and regression coverage.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-24",
        update_number=24,
        version="V0.1.23",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "Extended the provider deadline for full autonomous source sweeps after the "
                "first live run safely stopped at the normal answer timeout.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Short gameplay-video analysis now also has its own bounded media-aware request "
                "deadline without changing ordinary answer latency controls.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-25",
        update_number=25,
        version="V0.1.24",
        released_on=date(2026, 8, 31),
        notes=(
            ReleaseNote(
                ReleaseSection.FIXES,
                "Split autonomous update research into independent official and community "
                "passes after a second live provider timeout.",
            ),
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Successful official results now survive a slow community source pass, while "
                "the missed source group is recorded for the next retry.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Each source group now uses a faster fit-for-purpose model, a bounded search "
                "deadline, isolated domain filters, and separately recorded usage.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-26",
        update_number=26,
        version="V0.1.25",
        released_on=date(2026, 9, 1),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Added a member-readable ROTATIONS category with five read-only live indexes "
                "for daily loot, weekly missions, Descent, seasonal activity, and reset timing.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "ERIN now publishes current Escalation missions, targeted loot, and Prototype "
                "requisitions from a dated structured feed alongside active season events.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added local-time daily, weekly, vendor, Raid, and three-day Descent reset "
                "timers plus confidence-gated research for regional and weekly assignments.",
            ),
            ReleaseNote(
                ReleaseSection.PRIVACY_SAFETY,
                "Future, expired, weakly sourced, or uncorroborated rotation claims are withheld "
                "instead of being presented as current game information.",
            ),
            ReleaseNote(
                ReleaseSection.MAINTENANCE,
                "Rotation posts update in place, survive transient feed failures, persist their "
                "checkpoint, and can be inspected or refreshed through new staff commands.",
            ),
        ),
    ),
    Release(
        release_id="erin-update-27",
        update_number=27,
        version="V0.1.26",
        released_on=date(2026, 9, 1),
        notes=(
            ReleaseNote(
                ReleaseSection.HIGH_IMPACT,
                "Rebuilt daily targeted-loot reporting around current map images or complete "
                "typed location assignments, including the Pentagon, Coney Island, Dark Hours, "
                "and Iron Horse.",
            ),
            ReleaseNote(
                ReleaseSection.NEW_FEATURES,
                "Added regional and loot-category dividers with stable spatial then "
                "alphabetical ordering for missions, areas, Classified Assignments, Raids, and "
                "other locations.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Invaded rotations now require and display three Main Missions, the Invaded "
                "Stronghold, and Tidal Basin in progression order instead of accepting a partial "
                "weekly list.",
            ),
            ReleaseNote(
                ReleaseSection.FIXES,
                "Descent reports now require the current named pool and can include its full "
                "talent breakdown; Dark Zone reports require East, South, and West assignments.",
            ),
            ReleaseNote(
                ReleaseSection.IMPROVEMENTS,
                "Removed repeated evidence-gate placeholders and taught rotation research to run "
                "again immediately after daily and Descent resets.",
            ),
        ),
    ),
)
