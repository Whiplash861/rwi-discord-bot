"""September 11 research additions. Announcements are not live gameplay mechanics."""

from decimal import Decimal
from typing import Any

from rwi_bot.db.models import SourceType
from rwi_bot.services.knowledge import SourceEvidence

GAMESCOM = SourceEvidence(
    url="https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/73nxDOZb1RAeMlTekMYld0/the-division-2-at-gamescom-crossplay-echoes-of-central-park-and-red-horizon",
    title="Gamescom: Crossplay, Echoes of Central Park and Red Horizon",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.98"),
    publisher="Ubisoft",
    note=(
        "Announced August 26; re-read September 11. Roadmap announcements, not live "
        "feature availability."
    ),
)
ROAD_AHEAD = SourceEvidence(
    url="https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/4cnPM47xq6IoPvleXO1KHk/the-division-2-at-gamescom-survivors-elite-task-force-and-the-road-ahead",
    title="Survivors, Elite Task Force and the Road Ahead",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.98"),
    publisher="Ubisoft",
    note="Published August 27; re-read September 11.",
)
VODS = SourceEvidence(
    url="https://steamcommunity.com/games/2221490/announcements/detail/704403754821092332",
    title="The Division 2: Gamescom 2026 Panel VODs",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.95"),
    publisher="Ubisoft on Steam",
    note=(
        "September 1 official publisher announcement. Metadata inspected; full video not "
        "transcribed."
    ),
)
ARG = SourceEvidence(
    url="https://www.reddit.com/r/thedivision/comments/1w3vt25/spoiler_the_division_2_echoes_of_central_park_arg/",
    title="Echoes of Central Park ARG code hunt",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.70"),
    publisher="r/thedivision",
    note="September 1 player investigation, with concept-art links. Not proof of DLC mechanics.",
)
PREDICTIONS = SourceEvidence(
    url="https://www.reddit.com/r/thedivision/comments/1w65s96/central_perk_2026/",
    title="Central Park timing discussion",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.60"),
    publisher="r/thedivision",
    note="September 3 discussion. Community launch-date predictions are not announcements.",
)

OBSERVATION_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "subject": "Echoes of Central Park DLC confirmed preview and showcase",
        "content": {
            "as_of": "2026-09-11",
            "availability": "Upcoming expansion; not currently playable.",
            "confirmed": [
                "A distress call leads Agents toward Central Park, with rumors on the "
                "Upper West Side.",
                "The park was an outbreak-era burial ground; its later condition is a "
                "story mystery.",
                "The tone emphasizes fear and a darker atmosphere.",
                "The gameplay showcase is September 24, 2026 at 16:00 UTC (noon Eastern).",
            ],
            "unknown": (
                "Do not claim a confirmed release day, enemy roster, loot table or hidden "
                "gameplay system from this preview."
            ),
        },
        "sources": (GAMESCOM, ROAD_AHEAD, VODS),
    },
    {
        "subject": "Crossplay and Season 4 future changes versus current Red Horizon",
        "content": {
            "as_of": "2026-09-11",
            "announced_not_live": [
                "Crossplay is planned for November, enabled by default with an opt-out at "
                "character selection.",
                "Clans migrate, capacity becomes 100, and leaderboards reset at introduction.",
                "Season 4 plans include Prototype progression/customization and Escalation "
                "changes.",
            ],
            "guidance": (
                "Keep current recommendations on Red Horizon rules. Announced future "
                "systems are not current build capabilities."
            ),
        },
        "sources": (GAMESCOM, VODS),
    },
    {
        "subject": "Survivors versus Echoes of Central Park and Year 9",
        "content": {
            "as_of": "2026-09-11",
            "summary": (
                "Survivors is a separate upcoming experience, not the Central Park DLC or "
                "a current season activity."
            ),
            "announced_design": (
                "Winter Washington, changing weather and temperature, varied run lengths, "
                "randomized loot and dynamic routes/extractions are development goals, not "
                "guaranteed final mechanics."
            ),
            "tests": (
                "Closed-test signups are planned later in 2026. The August 31 ETF "
                "application deadline has already passed."
            ),
            "future": "Year 9 is confirmed; detailed plans await a later reveal.",
        },
        "sources": (ROAD_AHEAD, VODS),
    },
    {
        "subject": "Central Park hidden clues ARG and community predictions",
        "content": {
            "as_of": "2026-09-11",
            "evidence_status": (
                "Community-reported teaser investigation and speculation, not confirmed gameplay."
            ),
            "reported_clues": (
                "Players traced code fragments in concept art to a reward code and a "
                "backpack QR link to The Paper Route. Check the original art and current "
                "redemption availability before giving an acquisition instruction."
            ),
            "prediction": (
                "Some players expect a November launch near crossplay. This is "
                "speculation, not an announced date."
            ),
            "limitations": (
                "An ARG clue, ominous artwork or streamer reaction cannot establish "
                "zombies, new factions, stealth systems or unreleased item stats. Ask "
                "about spoilers before explaining puzzle solutions."
            ),
        },
        "sources": (ARG, PREDICTIONS),
    },
)
