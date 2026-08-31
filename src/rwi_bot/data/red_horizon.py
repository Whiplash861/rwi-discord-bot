from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from rwi_bot.data.red_horizon_encounters import COMPLETE_ENCOUNTER_RECORDS
from rwi_bot.data.red_horizon_raids_dz import RAID_AND_DZ_RECORDS
from rwi_bot.data.red_horizon_skills import RED_HORIZON_SKILL_TABLES
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
OFFICIAL_BRAND_BREAKDOWN_URL = (
    "https://canopy.ubisoft.com/AssetLink/kh506il172knvrt4x7c680hw03b8g63f.pdf"
)
OFFICIAL_BRAND_BREAKDOWN_SOURCE = SourceEvidence(
    url=OFFICIAL_BRAND_BREAKDOWN_URL,
    title="Red Horizon Gear Updates",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.990"),
    publisher="Ubisoft",
    supports_claim=True,
    note="Final Y8S3 Gear and Brand Set breakdown linked from the Red Horizon launch article.",
)
OFFICIAL_SKILL_BREAKDOWN_URL = (
    "https://canopy.ubisoft.com/AssetLink/1y4y4a237pd4u0o41c4te2j2t5c315k1.pdf"
)
OFFICIAL_SKILL_BREAKDOWN_SOURCE = SourceEvidence(
    url=OFFICIAL_SKILL_BREAKDOWN_URL,
    title="Red Horizon PvE and PvP Skill Changes",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.990"),
    publisher="Ubisoft",
    supports_claim=True,
    note="Final Y8S3 Skill table linked from the Red Horizon launch article.",
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
    sources: tuple[SourceEvidence, ...] = ()


RED_HORIZON_BRAND_BONUSES: dict[str, tuple[str, str, str]] = {
    "China Light Industries Corporation": (
        "+15% Explosive Damage",
        "+20% Status Effects (+8% PvP)",
        "+30% Skill Haste (+20% PvP)",
    ),
    "Electrique": (
        "+10% Status Effects",
        "+20% Hazard Protection (+20% PvP)",
        "+8% Skill Efficiency (+6% PvP)",
    ),
    "Empress International": (
        "+10% Skill Health",
        "+13% Skill Damage",
        "+8% Skill Efficiency",
    ),
    "Hana-U Corporation": (
        "+10% Skill Haste",
        "+13% Skill Damage",
        "+18% Weapon Damage",
    ),
    "Richter & Kaiser GmbH": (
        "+10% Skill Haste (+10% PvP)",
        "+40% Explosive Resistance",
        "+52% Repair Skills",
    ),
    "Wyvern Wear": (
        "+8% Skill Damage",
        "+20% Status Effects",
        "+45% Skill Duration",
    ),
    "5.11 Tactical": (
        "+12% Protection from Elites (+10% PvP)",
        "+100% Increased Threat (+100% PvP)",
        "+30% Hazard Protection",
    ),
    "Badger Tuff": (
        "+12% Shotgun Damage",
        "+10% Armor on Kill (+12% PvP)",
        "+15% Total Armor (+12% PvP)",
    ),
    "Belstone Armory": (
        "+1% Armor Regeneration",
        "+100% Increased Threat (+100% PvP)",
        "+36% Protection from Elites (+20% PvP)",
    ),
    "Gila Guard": (
        "+5% Total Armor",
        "+20% Hazard Protection (+15% PvP)",
        "+2% Armor Regeneration",
    ),
    "Golan Gear Ltd": (
        "+20% Explosive Resistance (+20% PvP)",
        "+1.5% Armor Regeneration",
        "+150% Increased Threat (+150% PvP)",
    ),
    "Habsburg Guard": (
        "+13% Headshot Damage",
        "+24% Marksman Rifle Damage",
        "+25% Status Effects",
    ),
    "Palisade Steelworks": (
        "+10% Armor on Kill",
        "+24% Protection from Elites (+15% PvP)",
        "+1 Skill Tier",
    ),
    "Lengmo": (
        "+15% Reload Speed (+15% PvP)",
        "+24% LMG Damage (+12% PvP)",
        "+30% Weapon Handling (+30% PvP)",
    ),
    "Airaldi Holdings": (
        "+12% Marksman Rifle Damage",
        "+26% Headshot Damage",
        "+5% Damage to Armor",
    ),
    "Ceska Vyroba s.r.o.": (
        "+8% Critical Hit Chance",
        "+24% Shotgun Damage (+12% PvP)",
        "+30% Hazard Protection (+30% PvP)",
    ),
    "Douglas & Harding": (
        "+24% Pistol Damage",
        "+20% Skill Health (+20% PvP)",
        "+50% Accuracy",
    ),
    "Fenris Group AB": (
        "+12% Assault Rifle Damage",
        "+32% Magazine Size (+20% PvP)",
        "+50% Stability",
    ),
    "Grupo Sombra S.A.": (
        "+13% Critical Hit Damage",
        "+20% Explosive Damage",
        "+39% Headshot Damage",
    ),
    "Imminence Armaments": (
        "+6% Weapon Damage",
        "+48% Pistol Damage (+22% PvP)",
        "+30% Skill Health (+30% PvP)",
    ),
    "Legatus S.p.A.": (
        "+15% Magazine Size (+10% PvP)",
        "+24% SMG Damage (+12% PvP)",
        "+105% Optimal Range (+75% PvP)",
    ),
    "Petrov Defense Group": (
        "+12% LMG Damage",
        "+15% Weapon Handling",
        "+50% Ammo Capacity",
    ),
    "Overlord Armaments": (
        "+12% Rifle Damage",
        "+30% Accuracy",
        "+30% Weapon Handling",
    ),
    "Royal Works": (
        "+5% Weapon Handling",
        "+24% LMG Damage (+12% PvP)",
        "+50% Accuracy (+40% PvP)",
    ),
    "Sokolov Concern": (
        "+12% SMG Damage",
        "+13% Critical Hit Damage",
        "+8% Critical Hit Chance",
    ),
    "Unit Alloys": (
        "+5% Rate of Fire",
        "+24% Assault Rifle Damage",
        "+50% Magazine Size",
    ),
    "Urban Lookout": (
        "+5% Weapon Handling (+10% PvP)",
        "+24% Marksman Rifle Damage (+12% PvP)",
        "+45% Skill Duration (+30% PvP)",
    ),
    "Walker, Harris & Co.": (
        "+6% Weapon Damage",
        "+5% Damage to Armor",
        "+10% Damage to Health",
    ),
    "Zwiadowka Sp. z o.o.": (
        "+15% Magazine Size",
        "+24% Rifle Damage",
        "+30% Weapon Handling",
    ),
}


RED_HORIZON_GEAR_SET_UPDATES: dict[str, dict[str, Any]] = {
    "Ortiz: Exuro": {
        "chest_talent": "Chain Combustion",
        "chest_effect": (
            "Enemies set ablaze by the Ortiz Incinerator Turret Prototype ignite other "
            "enemies within 10m."
        ),
        "backpack_talent": "Heatstroke",
        "backpack_effects": [
            "+40% amplified damage to enemies set on fire by the Ortiz Incinerator "
            "Turret Prototype",
            "+25% Ortiz Incinerator Turret Prototype range",
        ],
        "description_correction": (
            "The backpack description says Increased Weapon Damage, but the bonus is an amplifier."
        ),
    },
    "True Patriot": {
        "two_piece": "+15% Weapon Handling",
        "three_piece": "+30% Magazine Size",
        "four_piece_talent": "Red, White and Blue",
        "four_piece_rules": {
            "rotation_seconds": 2,
            "red": "+15% amplified damage taken",
            "white": "Shooting repairs the attacking agent's armor by 2% once per second",
            "blue": "-10% enemy damage dealt",
            "full_flag": (
                "Death under all three debuffs creates a 5m explosion equal to total health "
                "and armor; Named-enemy explosion damage is reduced."
            ),
        },
        "chest_talent": "Waving the Flag",
        "chest_rotation_seconds": 1,
        "backpack_talent": "Patriotic Boost",
        "backpack_values": {"red": "+30%", "white": "+5%", "blue": "-20%"},
    },
    "Aces & Eights": {
        "two_piece": ["+30% MMR Damage", "+30% Rifle Damage"],
        "three_piece": ["+30% Headshot Damage", "+30% Weapon Handling (+15% PvP)"],
        "four_piece_talent": "Dead Man's Hand",
        "four_piece_rules": (
            "Rifle or Marksman Rifle hits flip cards. After five cards, the next shot is "
            "amplified by 75%; Four of a Kind enhances four shots, Full House three, and "
            "Aces and Eights two. Headshots flip one additional card."
        ),
        "chest_talent": "No Limit",
        "chest_amplification": "+100%",
    },
    "Breaking Point": {
        "two_piece": ["+30% MMR Damage", "+30% Rifle Damage"],
        "three_piece": ["+30% Headshot Damage", "+30% Weapon Handling"],
        "four_piece_talent": "On Point",
        "four_piece_rules": (
            "Rifle or MMR hits grant stacks. Reloading grants +2% Weapon Handling and +4% "
            "Weapon Damage per stack for 20 seconds. No stacks are gained while active; "
            "expiry or a weapon switch refills the magazine, and switching while inactive "
            "also removes all stacks."
        ),
        "chest_talent": "Point of No Return",
        "chest_duration_seconds": 40,
        "backpack_talent": "Point of Honor",
        "backpack_weapon_damage_per_stack": "+9%",
    },
    "Hotshot": {
        "bonus_change": "The +30% Weapon Handling bonus moved from the 2-piece to 3-piece bonus.",
        "four_piece_talent": "Headache",
        "four_piece_cycle": [
            "First MMR headshot gives the next headshot +80% damage.",
            "Second consecutive MMR headshot gives +10% armor, or bonus armor when full, "
            "up to 50% of current armor.",
            "Third consecutive MMR headshot refills the magazine.",
            "From the fourth consecutive headshot kill onward, all three bonuses apply.",
            "Missing a headshot resets the cycle.",
        ],
    },
    "Concentrated Company": {
        "four_piece_talent": "Camaraderie",
        "four_piece_rules": (
            "Shooting marks an enemy for 10 seconds. When it dies, gain one stack of +3% "
            "Weapon Damage and +3% Critical Hit Damage for each ally or skill that helped, "
            "including yourself. Maximum 35 stacks; stacks decay every 10 seconds; maximum "
            "four marks."
        ),
        "backpack_talent": "One for All",
        "backpack_weapon_damage_per_stack": "+6%",
    },
    "Negotiator's Dilemma": {
        "four_piece_talent": "Crowd Control",
        "four_piece_rules": (
            "Critical hits mark enemies for 20 seconds, up to three marks. Critically hitting "
            "one marked enemy deals 60% of that damage to every other marked enemy. A marked "
            "enemy death grants +10% Critical Hit Damage, up to 10 stacks or until combat ends."
        ),
    },
    "Ongoing Directive": {
        "four_piece_talent": "Rules of Engagement",
        "four_piece_rules": (
            "Shooting a status-affected enemy marks it for 10 seconds. Killing it grants a "
            "full magazine of Hollow-Point Ammo to the active weapon and half a magazine of "
            "each party member's active weapon. Hollow-Point Ammo amplifies weapon damage by "
            "40% and applies bleed on hit."
        ),
        "chest_talent": "Parabellum Rounds",
        "chest_hollow_point_amplification": "+60% for the owner; does not apply to the party",
    },
    "Tipping Scales": {
        "four_piece_talent": "Throttle Control",
        "four_piece_rules": (
            "Shooting builds up to 50 stacks. Each stack grants +0.5% Weapon Handling and +5% "
            "Critical Hit Damage. Lose six stacks per second while not shooting, except while "
            "an enemy is Suppressed."
        ),
        "backpack_talent": "Snowball",
        "backpack_critical_hit_damage_per_stack": "+8%",
    },
}


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
        subject="Red Horizon Hostile Modifiers",
        entity_type="seasonal_modifier",
        claim_key="current_rules",
        content={
            "removal_rule": (
                "Setting the affected enemy on fire is the only permanent way to remove or "
                "reverse the hostile effect."
            ),
            "Draining Presence": (
                "Drains magazine ammunition and Pressure while the affected enemy is nearby."
            ),
            "Achilles' Heal": (
                "Breaking weak points or armor restores the affected enemy and nearby allies' "
                "Health while reducing Pressure."
            ),
            "Thousand Cuts": (
                "Enemy hits reduce Pressure and apply a stacking Damage Reduction debuff."
            ),
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
        subject="Red Horizon Dark Zone Rotation",
        entity_type="activity",
        claim_key="current_rotation_rules",
        content={
            "weekly_zone_count": 3,
            "pve_zone_count": 1,
            "pvp_zone_count": 2,
            "always_active_variants": ["Toxic", "Balanced"],
            "alternating_variants": ["Blackout", "Classic"],
        },
        context={"season": "Red Horizon", "mode": "dark_zone"},
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
    KnowledgeSeed(
        subject="Red Horizon PvP Stat Display",
        entity_type="system",
        claim_key="current_behavior",
        content={
            "inventory": (
                "PvP weapon damage values display alongside PvE values and stats switch to "
                "their PvP values upon entering a PvP environment."
            ),
            "shooting_range": (
                "PvP Normalization and Global PvP Balance overrides can be enabled in the "
                "Shooting Range."
            ),
            "normalization_button": "Temporarily unavailable while its UI is updated.",
        },
        context={"season": "Red Horizon", "mode": "pvp"},
    ),
    KnowledgeSeed(
        subject="Red Horizon Classified Assignments",
        entity_type="activity",
        claim_key="current_schedule_and_access",
        content={
            "assignments": {
                "The District Mall Inferno": "August 27, 2026",
                "The Georgetown Dead Zone": "October 15, 2026",
            },
            "access": "Dedicated Assignments map tab; unlocks at Level 30.",
            "purchase_required": True,
        },
        context={"season": "Red Horizon", "mode": "pve"},
    ),
    KnowledgeSeed(
        subject="Red Horizon Retaliation Events",
        entity_type="activity",
        claim_key="current_schedule",
        content={
            "project_chain": "September 8 through September 22, 2026",
            "project_chain_reward": "One eligible outfit token after completing the chain",
            "retaliation_surge": "September 8 through September 15, 2026",
            "retaliation_surge_effect": "Double Retaliation Faction Materials from all sources",
        },
        context={"season": "Red Horizon", "mode": "pve"},
    ),
    KnowledgeSeed(
        subject="Ballistic Shield",
        entity_type="skill_family",
        claim_key="current_pve_stats_and_overcharge",
        content={
            "variants": [
                "Bulwark Shield",
                "Crusader Shield",
                "Deflector Shield",
                "Striker Shield",
            ],
            "common_pve_overcharge_effect": "Shield Wall: the shield is invulnerable.",
            "pvp_overcharge_functionality": False,
            "pve": {
                "Bulwark Shield": {
                    "cooldown_seconds": 20,
                    "base_health": 2654490,
                    "health_tiers_1_to_6_percent": [67, 133, 200, 266, 333, 400],
                    "overcharge_health_percent": 400,
                    "base_active_regeneration_per_second": 79635,
                    "active_regeneration_tiers_1_to_6_percent": [20, 40, 60, 80, 100, 120],
                    "overcharge_active_regeneration_percent": 500,
                    "base_holstered_regeneration_per_second": 132725,
                    "holstered_regeneration_tiers_1_to_6_percent": [5, 10, 15, 20, 25, 40],
                    "overcharge_holstered_regeneration_percent": 40,
                },
                "Crusader Shield": {
                    "cooldown_seconds": 20,
                    "base_health": 1327245,
                    "health_tiers_1_to_6_percent": [40, 66, 100, 150, 200, 250],
                    "overcharge_health_percent": 250,
                    "base_active_regeneration_per_second": 39817,
                    "active_regeneration_tiers_1_to_6_percent": [10, 20, 30, 40, 50, 60],
                    "overcharge_active_regeneration_percent": 500,
                    "base_holstered_regeneration_per_second": 66362,
                    "holstered_regeneration_tiers_1_to_6_percent": [5, 10, 15, 20, 25, 40],
                    "overcharge_holstered_regeneration_percent": 40,
                },
                "Deflector Shield": {
                    "cooldown_seconds": 20,
                    "base_health": 2123592,
                    "health_tiers_1_to_6_percent": [40, 66, 100, 150, 200, 250],
                    "overcharge_health_percent": 250,
                    "base_active_regeneration_per_second": 63708,
                    "active_regeneration_tiers_1_to_6_percent": [10, 20, 30, 40, 50, 60],
                    "overcharge_active_regeneration_percent": 60,
                    "base_holstered_regeneration_per_second": 106180,
                    "holstered_regeneration_tiers_1_to_6_percent": [5, 10, 15, 20, 25, 40],
                    "overcharge_holstered_regeneration_percent": 40,
                    "base_deflector_damage": 80465,
                    "deflector_damage_tiers_1_to_6_percent": [10, 20, 30, 40, 50, 60],
                    "overcharge_deflector_damage_percent": 100,
                },
                "Striker Shield": {
                    "cooldown_seconds": 20,
                    "base_damage_bonus_per_enemy_percent": 5,
                    "damage_bonus_tiers_1_to_6_percentage_points": [1, 1.2, 1.4, 1.6, 1.8, 2],
                    "overcharge_damage_bonus_percentage_points": 2.5,
                    "buff_angle_degrees": 45,
                    "buff_range_meters": 10,
                    "base_health": 1327245,
                    "health_tiers_1_to_6_percent": [40, 66, 100, 150, 200, 250],
                    "overcharge_health_percent": 400,
                    "base_active_regeneration_per_second": 39817,
                    "active_regeneration_tiers_1_to_6_percent": [10, 20, 30, 40, 50, 60],
                    "overcharge_active_regeneration_percent": 60,
                    "base_holstered_regeneration_per_second": 66362,
                    "holstered_regeneration_tiers_1_to_6_percent": [5, 10, 15, 20, 25, 40],
                    "overcharge_holstered_regeneration_percent": 100,
                },
            },
        },
        context={"season": "Red Horizon", "mode": "pve_and_pvp", "level": 40},
        confidence=0.99,
        sources=(OFFICIAL_SOURCE, OFFICIAL_SKILL_BREAKDOWN_SOURCE),
    ),
    *(
        KnowledgeSeed(
            subject=display_name,
            entity_type="skill_variant",
            claim_key="current_base_tiers_and_overcharge",
            content=record,
            context={
                "season": "Red Horizon",
                "mode": record["mode"],
                "source": "final_y8s3_skill_table",
            },
            confidence=0.99,
            sources=(OFFICIAL_SOURCE, OFFICIAL_SKILL_BREAKDOWN_SOURCE),
        )
        for display_name, record in RED_HORIZON_SKILL_TABLES.items()
    ),
    *(
        KnowledgeSeed(
            subject=gear_set,
            entity_type="gear_set",
            claim_key="red_horizon_current_rules",
            content=content,
            context={"season": "Red Horizon", "mode": "pve_and_pvp"},
            confidence=0.99,
            sources=(OFFICIAL_SOURCE, OFFICIAL_BRAND_BREAKDOWN_SOURCE),
        )
        for gear_set, content in RED_HORIZON_GEAR_SET_UPDATES.items()
    ),
    *(
        KnowledgeSeed(
            subject=brand,
            entity_type="brand_set",
            claim_key="current_bonuses",
            content={
                "one_piece": bonuses[0],
                "two_piece": bonuses[1],
                "three_piece": bonuses[2],
            },
            context={"season": "Red Horizon", "mode": "pve_and_pvp"},
            confidence=0.99,
            sources=(OFFICIAL_SOURCE, OFFICIAL_BRAND_BREAKDOWN_SOURCE),
        )
        for brand, bonuses in RED_HORIZON_BRAND_BONUSES.items()
    ),
    *(
        KnowledgeSeed(
            subject=record["subject"],
            entity_type=record["entity_type"],
            claim_key=record["claim_key"],
            content=record["content"],
            context=record["context"],
            confidence=record["confidence"],
            sources=record["sources"],
        )
        for record in RAID_AND_DZ_RECORDS
    ),
    *(
        KnowledgeSeed(
            subject=record["subject"],
            entity_type=record["entity_type"],
            claim_key=record["claim_key"],
            content=record["content"],
            context=record["context"],
            confidence=record["confidence"],
            sources=record["sources"],
        )
        for record in COMPLETE_ENCOUNTER_RECORDS
    ),
)
