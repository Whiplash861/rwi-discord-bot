from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from rwi_bot.db.models import KnowledgeStatus, SourceType
from rwi_bot.services.knowledge import SourceEvidence

GAME_VERSION = "Y8S3 Red Horizon"
OFFICIAL_SOURCE_URL = (
    "https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/"
    "4mrYiFPIyKpzpoqshDQk80/the-division-2-red-horizon"
)
OFFICIAL_SOURCE = SourceEvidence(
    url=OFFICIAL_SOURCE_URL,
    title="The Division 2: Red Horizon",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.980"),
    publisher="Ubisoft",
    supports_claim=True,
    note="Official Red Horizon launch article published August 26, 2026.",
)


@dataclass(frozen=True, slots=True)
class KnowledgeSeed:
    subject: str
    entity_type: str
    claim_key: str
    content: dict[str, Any]
    context: dict[str, Any]
    confidence: float = 0.98
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE


RED_HORIZON_SEEDS: tuple[KnowledgeSeed, ...] = (
    KnowledgeSeed(
        subject="Red Horizon Under Pressure",
        entity_type="seasonal_modifier",
        claim_key="current_rules",
        content={
            "global_modifier": "Under Pressure",
            "gauge_sources": [
                "kills",
                "headshots",
                "multikills",
                "skill kills",
                "status effect kills",
                "fire kills",
                "group member kills",
            ],
            "default_primary_bonus": "status effects",
            "replaceable_primary_bonuses": [
                "signature weapon damage",
                "hazard protection",
            ],
            "active_modifiers": {
                "Fiery Aura": ["armor regeneration", "damage resistance", "burn"],
                "Vicarious Combustion": ["headshot damage", "burn spread"],
                "Signed, Shield, Delivered": [
                    "skill efficiency",
                    "signature weapon performance",
                    "shield health",
                    "shield active regeneration",
                ],
            },
            "passive_modifier_count": 20,
        },
        context={"season": "Red Horizon", "mode": "seasonal"},
    ),
    KnowledgeSeed(
        subject="Red Horizon Brand and Gear Set Update",
        entity_type="balance_update",
        claim_key="current_rules",
        content={
            "gear_set_focus": ["red core", "Ortiz: Exuro", "True Patriot"],
            "brand_bonuses_removed": [
                "shock resistance",
                "health",
                "incoming repairs",
                "swap speed",
            ],
            "brand_bonus_added": "protection from elites",
            "new_brand_sets_planned": False,
            "future_item_direction": "named pieces on existing brands",
        },
        context={"season": "Red Horizon", "mode": "pve_and_pvp"},
    ),
    KnowledgeSeed(
        subject="Steel & Sons ACR",
        entity_type="weapon",
        claim_key="red_horizon_changes",
        content={
            "base_stability": "increased",
            "maximum_stacks": 4,
            "weak_point_effect": {
                "amplified_damage": 0.30,
                "duration_seconds": 5,
            },
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Determined",
        entity_type="weapon_talent",
        claim_key="current_behavior",
        content={
            "converted_headshot_kill_retriggers": False,
            "behavior": "Functions like Perfect Determined; converted headshot kills do not chain.",
            "former_chain_replacement": "Iron Will Exotic Chest / Resolved",
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Fafnir",
        entity_type="exotic_weapon",
        claim_key="current_stats",
        content={
            "weapon_type": "shotgun",
            "talent": "Dragon's Breath",
            "burn_chance_per_shot": 0.40,
            "weapon_damage_amplification_from_status_effect_bonus": 0.50,
            "mods": {
                "optics_critical_hit_chance": 0.15,
                "magazine_rounds": 5,
                "underbarrel_weapon_handling": 0.10,
            },
            "caveat": "Burn application remains subject to status-effect diminishing returns.",
        },
        context={"season": "Red Horizon", "mode": "pve_and_pvp"},
    ),
    KnowledgeSeed(
        subject="Iron Will",
        entity_type="exotic_gear",
        claim_key="current_stats",
        content={
            "slot": "chest",
            "talent": "Resolved",
            "effect": "Next body shot is considered a headshot.",
            "pve_cooldown_seconds": 2,
            "pvp_cooldown_seconds": 3,
            "allowed_weapon_types": ["marksman rifle", "rifle", "pistol"],
        },
        context={"season": "Red Horizon", "mode": "pve_and_pvp"},
    ),
    KnowledgeSeed(
        subject="Ember Engine",
        entity_type="gear_set",
        claim_key="current_stats",
        content={
            "two_piece_skill_efficiency": 0.08,
            "three_piece_status_effect": 0.30,
            "four_piece_talent": "Spontaneous Combustion",
            "four_piece_burn_chance": 0.40,
            "burn_on_burn_damage_bonus": 0.25,
            "chest_talent": "Flashpoint",
            "chest_burn_chance": 0.60,
            "backpack_talent": "White Hot",
            "backpack_burn_duration_bonus": 0.50,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Trick Shot",
        entity_type="named_gear",
        claim_key="current_stats",
        content={
            "brand": "Imminence Armaments",
            "slot": "chest",
            "talent": "Perfect Reassigned",
            "effect": "A kill adds one random special-ammo round to the sidearm.",
            "cooldown_seconds": 8,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Rushdown",
        entity_type="named_gear",
        claim_key="current_stats",
        content={
            "brand": "Richter & Kaiser GmbH",
            "slot": "chest",
            "talent": "Tag Team",
            "active_cooldown_reduction_seconds": 12,
            "cooldown_seconds": 4,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Melon Baller",
        entity_type="named_gear",
        claim_key="current_stats",
        content={
            "brand": "Airaldi Holdings",
            "slot": "backpack",
            "talent": "Perfect Concussion",
            "headshot_total_weapon_damage": 0.20,
            "headshot_duration_seconds": 1.5,
            "marksman_rifle_duration_seconds": 5,
            "headshot_kill_total_weapon_damage": 0.15,
            "headshot_kill_duration_seconds": 10,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Keeper",
        entity_type="named_gear",
        claim_key="current_stats",
        content={
            "brand": "5.11 Tactical",
            "slot": "backpack",
            "talent": "Perfect Protector",
            "self_bonus_armor": 0.25,
            "ally_bonus_armor_from_owners_armor": 0.35,
            "duration_seconds": 3,
            "cooldown_seconds": 3,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Teapot",
        entity_type="named_weapon",
        claim_key="current_stats",
        content={
            "talent": "Perfect Boiling Point",
            "magazine_fraction_with_negative_critical_chance": 0.48,
            "critical_hit_chance_during_first_fraction": -1.0,
            "critical_hit_chance_during_remaining_fraction": 1.0,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Steamer",
        entity_type="named_weapon",
        claim_key="current_stats",
        content={
            "talent": "Perfect Boiling Point",
            "magazine_fraction_with_negative_critical_chance": 0.48,
            "critical_hit_chance_during_first_fraction": -1.0,
            "critical_hit_chance_during_remaining_fraction": 1.0,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Boiling Point",
        entity_type="weapon_talent",
        claim_key="current_stats",
        content={
            "magazine_fraction_with_negative_critical_chance": 0.53,
            "critical_hit_chance_during_first_fraction": -1.0,
            "critical_hit_chance_during_remaining_fraction": 1.0,
            "perfect_version_negative_fraction": 0.48,
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
    KnowledgeSeed(
        subject="Toxic Dark Zone",
        entity_type="activity",
        claim_key="current_rules_and_rewards",
        content={
            "activity_type": "permanent pve dark zone",
            "normalization": "level 40",
            "pvp_overrides_active": False,
            "prototype_gear_normalized": True,
            "landmark_chest_contaminated_cache_chance": 0.20,
            "contaminated_cache_pool": [
                "exclusive gear sets",
                "raid gear sets",
                "legacy dark zone weapons",
                "named items",
                "exotics",
            ],
        },
        context={"season": "Red Horizon", "mode": "pve"},
    ),
    KnowledgeSeed(
        subject="Blackout Dark Zone",
        entity_type="activity",
        claim_key="current_rules_and_rewards",
        content={
            "activity_type": "pvevp dark zone",
            "normalization": False,
            "global_pvp_balance": True,
            "shd_active": True,
            "expertise_active": True,
            "rogue_protocol_active": True,
            "prototype_base_stats_uncapped": True,
            "prototype_augments_use_pvp_values": True,
            "heroic_quality_loot": True,
            "additional_contaminated_item_chance": 0.20,
        },
        context={"season": "Red Horizon", "mode": "pvevp"},
    ),
    KnowledgeSeed(
        subject="Red Horizon PvP Dark Zone Prototype Drops",
        entity_type="acquisition",
        claim_key="current_drop_rates",
        content={
            "special_loot_pool_additions": [
                "Ortiz: Reficere",
                "Caduceus",
                "Nurse's Kneepads",
            ],
            "prototype_drop_rates": {
                "normal_mid": 0.002,
                "elite_mid": 0.005,
                "elite_high": 0.002,
                "boss_mid": 0.01,
                "boss_high": 0.02,
            },
            "exotic_component_rates": {
                "challenging_phoenix_crate": 0.33,
                "challenging_boss": 0.40,
                "heroic_phoenix_crate": 0.40,
                "heroic_boss": 0.48,
            },
        },
        context={"season": "Red Horizon", "mode": "pvp_dark_zone"},
    ),
    KnowledgeSeed(
        subject="Red Horizon Blueprints and Targeted Loot",
        entity_type="acquisition",
        claim_key="current_availability",
        content={
            "general_loot_pool_materials_and_blueprints": [
                "True Patriot",
                "Ongoing Directive",
                "Unit Alloys",
                "Royal Works",
                "Edelweiss",
                "Concentrated Company",
                "Core Strength",
                "Ortiz: Reficere",
            ],
            "inaya_blueprints_owner_unlock_required": [
                "Agitator",
                "Investor",
                "Caduceus",
                "Nurse's Kneepads",
                "Whiplash",
                "Underboss",
            ],
            "targeted_loot_additions": ["Caduceus", "Nurse's Kneepads"],
        },
        context={"season": "Red Horizon", "mode": "current"},
    ),
)
