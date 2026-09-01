from __future__ import annotations

import re
from dataclasses import dataclass

from rwi_bot.data.red_horizon import (
    OFFICIAL_BRAND_BREAKDOWN_URL,
    OFFICIAL_SKILL_BREAKDOWN_URL,
    OFFICIAL_SOURCE_URL,
)
from rwi_bot.services.language import normalize_text


@dataclass(frozen=True, slots=True)
class KnowledgeDomain:
    key: str
    title: str
    aliases: tuple[str, ...]
    required_facets: tuple[str, ...]
    research_targets: tuple[str, ...] = ()


PROTOTRACK_WIKI = "https://prototrack.gg/division2-wiki.php"


KNOWLEDGE_SYLLABUS: tuple[KnowledgeDomain, ...] = (
    KnowledgeDomain(
        key="exotic_gear",
        title="Exotic Gear",
        aliases=("exotic gear", "exotic armor", "exotic chest", "exotic backpack"),
        required_facets=(
            "slot and core/secondary attributes",
            "talent text and activation limits",
            "acquisition and reconfiguration route",
            "PvE/PvP differences",
            "legal build constraints and material interactions",
        ),
        research_targets=("https://prototrack.gg/exotic-gear.php",),
    ),
    KnowledgeDomain(
        key="exotic_weapons",
        title="Exotic Weapons",
        aliases=("exotic weapon", "exotic weapons", "exotic gun", "exotic rifle"),
        required_facets=(
            "weapon family and base behavior",
            "talent and mod text",
            "acquisition and reconfiguration route",
            "PvE/PvP differences",
            "supported and prohibited interactions",
        ),
        research_targets=("https://prototrack.gg/exotic-gear.php",),
    ),
    KnowledgeDomain(
        key="named_items",
        title="Named Items",
        aliases=("named item", "named items", "named gear", "named weapon"),
        required_facets=(
            "base item, slot, brand, and weapon family",
            "Perfect talent or unique fixed attribute",
            "normal and Prototype values where applicable",
            "acquisition pool and blueprint availability",
            "PvE/PvP differences",
        ),
        research_targets=(
            "https://prototrack.gg/named-gear.php",
            "https://prototrack.gg/named-weapons.php",
        ),
    ),
    KnowledgeDomain(
        key="standard_arsenal",
        title="Normal Gear and Weapons",
        aliases=(
            "normal gear",
            "normal weapon",
            "regular gear",
            "regular weapon",
            "high-end gear",
            "high-end weapon",
        ),
        required_facets=(
            "rarity, slot or weapon family, and base attributes",
            "roll ranges and mod slots",
            "compatible talent pool",
            "acquisition and crafting availability",
            "PvE/PvP and Prototype differences",
        ),
        research_targets=(PROTOTRACK_WIKI,),
    ),
    KnowledgeDomain(
        key="talents",
        title="Talents and Perfect Variants",
        aliases=("talent", "talents", "perfect talent", "perfect variant"),
        required_facets=(
            "exact current text and eligible slot or weapon families",
            "activation, deactivation, duration, cooldown, and stack rules",
            "Perfect variant and its Named item",
            "PvE/PvP values",
            "supported exceptions and interactions",
        ),
        research_targets=(
            "https://prototrack.gg/weapon-talents.php",
            "https://prototrack.gg/gear-talents.php",
        ),
    ),
    KnowledgeDomain(
        key="rarity",
        title="Item Rarity",
        aliases=(
            "rarity",
            "worn",
            "standard rarity",
            "superior",
            "high-end",
            "gear set rarity",
            "prototype rarity",
        ),
        required_facets=(
            "rarity hierarchy and color",
            "attribute, talent, and mod-slot rules",
            "level and activity availability",
            "recalibration, optimization, and Expertise eligibility",
            "Prototype differences",
        ),
        research_targets=(PROTOTRACK_WIKI,),
    ),
    KnowledgeDomain(
        key="difficulty",
        title="Difficulty",
        aliases=(
            "difficulty",
            "story difficulty",
            "normal difficulty",
            "hard difficulty",
            "challenging",
            "heroic",
            "legendary",
            "master difficulty",
        ),
        required_facets=(
            "availability by activity",
            "enemy health, damage, archetype, and checkpoint changes",
            "loot quality and XP effects",
            "group scaling and respawn rules",
            "interaction with Directives and special modes",
        ),
    ),
    KnowledgeDomain(
        key="directives",
        title="Directives",
        aliases=(
            "directive",
            "directives",
            "fog of war",
            "pistolero",
            "hard to earn",
            "no regen",
        ),
        required_facets=(
            "exact rule and affected resource or HUD system",
            "current seasonal availability",
            "XP effect",
            "activity and difficulty compatibility",
            "build counters and important exceptions",
        ),
    ),
    KnowledgeDomain(
        key="mission_types",
        title="Mission Types",
        aliases=(
            "mission type",
            "story mission",
            "invaded mission",
            "manhunt mission",
            "raid",
            "incursion",
            "expedition",
        ),
        required_facets=(
            "access and player-count requirements",
            "difficulty and checkpoint rules",
            "objectives and encounter structure",
            "unique rewards and acquisition locks",
            "weekly, seasonal, or invasion rotation",
        ),
    ),
    KnowledgeDomain(
        key="skills",
        title="Skills and Skill Tiers",
        aliases=("skill", "skills", "skill tier", "overcharge"),
        required_facets=(
            "platform and every variant",
            "base stats and Skill Tier 1-6 scaling",
            "Overcharge values and special effects",
            "PvE/PvP differences",
            "specialization locks, mods, talents, and material interactions",
        ),
        research_targets=(OFFICIAL_SKILL_BREAKDOWN_URL,),
    ),
    KnowledgeDomain(
        key="progression_costs",
        title="Resources, Crafting, Tinkering, Optimization, and ProtoLab Costs",
        aliases=(
            "resource",
            "resources",
            "crafting cost",
            "tinkering",
            "optimization cost",
            "expertise cost",
            "protolab",
            "prototype cost",
        ),
        required_facets=(
            "resource names and inventory caps",
            "exact cost by item type and upgrade step",
            "crafting, recalibration, optimization, Expertise, and ProtoLab distinctions",
            "blueprint and station requirements",
            "legitimate acquisition and efficient farming routes",
        ),
        research_targets=(
            "https://prototrack.gg/division2-costs.php",
            "https://prototrack.gg/prototype-info.php",
        ),
    ),
    KnowledgeDomain(
        key="special_missions",
        title="Special Missions and Activities",
        aliases=(
            "descent",
            "summit",
            "countdown",
            "classified assignment",
            "special mission",
            "special activity",
            "escalation",
        ),
        required_facets=(
            "access, group size, matchmaking, and run structure",
            "difficulty, modifiers, and failure rules",
            "vendors, currencies, and reward pools",
            "bosses and unique mechanics",
            "rotation and acquisition exclusives",
        ),
        research_targets=("https://prototrack.gg/escalation-info.php",),
    ),
    KnowledgeDomain(
        key="lore",
        title="Lore",
        aliases=("lore", "story", "character", "echo", "comm", "collectible"),
        required_facets=(
            "character, faction, location, and chronology",
            "primary collectible, mission, or official narrative evidence",
            "confirmed fact versus theory",
            "spoiler scope",
            "Red Horizon continuity impact",
        ),
    ),
    KnowledgeDomain(
        key="enemy_factions",
        title="Enemy Factions and Archetypes",
        aliases=(
            "enemy faction",
            "enemy archetype",
            "hyenas",
            "rikers",
            "cleaners",
            "black tusk",
            "true sons",
            "outcasts",
            "hunters",
        ),
        required_facets=(
            "faction identity, leadership, territory, and lore",
            "normal, veteran, elite, and Named archetypes",
            "weapons, skills, weak points, and status threats",
            "difficulty-dependent behavior",
            "safe counterplay and encounter priorities",
        ),
    ),
    KnowledgeDomain(
        key="buildcraft",
        title="Buildcraft, Roles, and Content Fit",
        aliases=(
            "buildcraft",
            "build advice",
            "team composition",
            "healer build",
            "tank build",
            "damage build",
            "skill build",
            "sniper build",
        ),
        required_facets=(
            "legal item and Exotic limits",
            "cores, attributes, mods, talents, weapons, skills, and specialization",
            "activation loop and intended combat range",
            "team role, content fit, and legitimate substitutions",
            "tiered pros, cons, failure modes, and profile-aware tradeoffs",
        ),
    ),
    KnowledgeDomain(
        key="combat_math",
        title="Combat Statistics and Damage Mathematics",
        aliases=(
            "damage math",
            "damage formula",
            "critical hit chance",
            "critical hit damage",
            "headshot damage",
            "damage to armor",
            "damage to health",
            "damage to targets out of cover",
        ),
        required_facets=(
            "base and additive Weapon Damage bucket",
            "Total Weapon Damage and shared HSD/CHD bucket",
            "armor, health, and out-of-cover target layers",
            "independent amplifiers and correctly classified team buffs",
            "activation conditions, caps, formula substitutions, and running arithmetic",
        ),
    ),
    KnowledgeDomain(
        key="raids",
        title="Raids, Encounters, and Team Roles",
        aliases=(
            "operation dark hours",
            "dark hours",
            "operation iron horse",
            "iron horse",
            "raid boss",
            "raid role",
        ),
        required_facets=(
            "encounters and bosses in progression order",
            "objectives, arena controls, damage windows, and wipe conditions",
            "team positions, callouts, and generalized roles",
            "encounter-specific builds, skills, and safe substitutions",
            "intended mechanics without skips, cheeses, bugs, or exploits",
        ),
    ),
    KnowledgeDomain(
        key="dark_zone",
        title="Dark Zone Rules and Builds",
        aliases=(
            "dark zone",
            "normalized dz",
            "invaded dz",
            "blackout dz",
            "toxic dz",
            "rogue agent",
            "extraction",
        ),
        required_facets=(
            "normalization, invaded, Blackout, and event-specific rules",
            "landmarks, contamination, extraction, rogue, SHD, and checkpoint systems",
            "PvE and PvP damage/stat differences",
            "solo and group role builds with counterplay",
            "reward loops and legitimate farming without exploits",
        ),
    ),
    KnowledgeDomain(
        key="progression",
        title="Progression and Endgame Systems",
        aliases=(
            "shd level",
            "watch level",
            "expertise level",
            "proficiency",
            "season level",
            "journey",
            "priority objective",
        ),
        required_facets=(
            "unlock requirements and account or character scope",
            "level, SHD, Proficiency, Expertise, and seasonal progression distinctions",
            "legitimate XP and material routes",
            "caps, costs, normalization, and content exclusions",
            "current seasonal changes and known issues",
        ),
    ),
    KnowledgeDomain(
        key="live_service",
        title="Current Season, Patches, and Known Issues",
        aliases=(
            "red horizon",
            "current season",
            "patch notes",
            "title update",
            "known issue",
            "bug status",
            "maintenance",
        ),
        required_facets=(
            "current version, platform, and publication date",
            "official patch-note wording and affected systems",
            "live Known Issues status and workarounds",
            "fixed, investigating, planned, and historical distinctions",
            "impact on builds, acquisition, activities, and stored ERIN knowledge",
        ),
    ),
    KnowledgeDomain(
        key="incursion_bosses",
        title="Incursion Bosses and Mechanics",
        aliases=(
            "incursion boss",
            "wright",
            "lovebirds",
            "steel family",
            "broken rain boss",
            "paradise lost boss",
        ),
        required_facets=(
            "encounter order, arena, and failure conditions",
            "boss attacks, immunity, weak points, and damage windows",
            "team roles, switches, valves, kiting, and other mechanics",
            "add waves and priority targets",
            "legitimate strategies and unique rewards",
        ),
    ),
)


def identify_knowledge_domains(question: str) -> tuple[KnowledgeDomain, ...]:
    normalized = normalize_text(question)
    return tuple(
        domain
        for domain in KNOWLEDGE_SYLLABUS
        if any(_contains(normalized, alias) for alias in domain.aliases)
    )


def knowledge_scope_prompt(question: str) -> str | None:
    domains = identify_knowledge_domains(question)
    if not domains:
        return None
    blocks: list[str] = []
    for domain in domains:
        facets = "; ".join(domain.required_facets)
        block = f"Knowledge domain: {domain.title}. Material completeness facets: {facets}."
        if domain.research_targets:
            targets = ", ".join(domain.research_targets)
            block += (
                " Discovery targets (not evidence by themselves; verify freshness and "
                f"corroborate mutable claims): {targets}."
            )
        blocks.append(block)
    return "\n".join(blocks)


def _contains(text: str, alias: str) -> bool:
    normalized_alias = normalize_text(alias)
    return re.search(rf"(?<!\w){re.escape(normalized_alias)}(?!\w)", text) is not None


CURRENT_Y8S3_PRIMARY_REFERENCES = (
    OFFICIAL_SOURCE_URL,
    OFFICIAL_BRAND_BREAKDOWN_URL,
    OFFICIAL_SKILL_BREAKDOWN_URL,
)
