from __future__ import annotations

from typing import Any

BOT_DISPLAY_NAME = "ERIN"
BOT_EXPANDED_NAME = "Enhanced Reconnaissance, Intelligence, and Navigation"

DIVISION_COMMANDER = "Division Commander"
DIVISION_COORDINATOR = "Division Coordinator"
TECHNICIAN = "Technician"
AGENT = "Agent"
XBOX = "Xbox"
PC = "PC"
PS = "PS"
ROGUE_AGENT = "Rogue Agent"
RAID_INCURSION_MATCHMAKING = "Raid & Incursion Matchmaking"

START_HERE = "START HERE"
ALLIANCE_HUB = "ALLIANCE HUB"
MATCHMAKING = "MATCHMAKING"
ROTATIONS = "ROTATIONS"
ADMINISTRATION = "ADMINISTRATION"

WELCOME = "welcome"
GENERAL_CHAT = "general-chat"
PASSIVE_GENERAL_CHANNELS = (GENERAL_CHAT, "general")


def is_passive_general(channel: Any) -> bool:
    """General text channels and their threads are observation-only."""
    name = getattr(getattr(channel, "parent", None), "name", None) or getattr(channel, "name", "")
    normalized = str(name).casefold().replace("_", "-")
    return normalized in PASSIVE_GENERAL_CHANNELS or normalized.startswith("general-")


ASK_RWI = "ask-rwi"
COMMUNITY_BUILDS = "community-builds"
COMMUNITY_LOADOUT_CHANNELS = (COMMUNITY_BUILDS, "community-loadouts")
ERIN_PATCH_NOTES = "erin-patch-notes"
GAME_UPDATES = "division-updates"
GALLERY = "gallery"
NSFW_CHAT = "nsfw-chat"
XBOX_MATCHMAKING = "xbox-matchmaking"
PC_MATCHMAKING = "pc-matchmaking"
PS_MATCHMAKING = "ps-matchmaking"
SCHEDULED_OPERATIONS = "scheduled-operations"
DAILY_TARGETED_LOOT = "daily-targeted-loot"
WEEKLY_MISSION_ROTATIONS = "weekly-mission-rotations"
DESCENT_ROTATION = "descent-rotation"
SEASONAL_ROTATIONS = "seasonal-rotations"
DARK_ZONE_ROTATIONS = "dark-zone-rotations"
VENDORS = "vendors"
RESET_TIMERS = "reset-timers"
COUNCIL = "council"
COUNCIL_VOICE = "Council Meeting Room"
ANNOTATIONS = "annotations"
DISCIPLINARY_LOG = "disciplinary-log"
WORKSHOP = "workshop"
TECHNICIAN_LAB = "technician-lab"
ERIN_KNOWLEDGE = "erin-knowledge"
BOT_OPS = "rwi-bot-ops"

PLATFORM_ROLES = (XBOX, PC, PS)
PROTECTED_ROLES = (DIVISION_COMMANDER, DIVISION_COORDINATOR, TECHNICIAN)
ROTATION_CHANNELS = (
    DAILY_TARGETED_LOOT,
    WEEKLY_MISSION_ROTATIONS,
    DESCENT_ROTATION,
    SEASONAL_ROTATIONS,
    DARK_ZONE_ROTATIONS,
    VENDORS,
    RESET_TIMERS,
)
