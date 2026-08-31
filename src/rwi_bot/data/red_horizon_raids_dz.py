# ruff: noqa: E501
from __future__ import annotations

from decimal import Decimal
from typing import Any

from rwi_bot.db.models import SourceType
from rwi_bot.services.knowledge import SourceEvidence

RED_HORIZON_FINAL_SOURCE = SourceEvidence(
    url=(
        "https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/"
        "4mrYiFPIyKpzpoqshDQk80/the-division-2-red-horizon"
    ),
    title="The Division 2: Red Horizon",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.980"),
    publisher="Ubisoft",
    supports_claim=True,
    note="Official Red Horizon launch article published August 26, 2026.",
)

INTO_THE_DARK_SOURCE = SourceEvidence(
    url=(
        "https://www.ubisoft.com/en-us/game/the-division/the-division-2/news-updates/"
        "2ViysTJslvmkyLSK0sFRRD/the-division-2-into-the-dark-fight-hyenas-venture-"
        "into-dark-zones-and-a-new-toxic-pve-experience"
    ),
    title="The Division 2 Into the Dark: Dark Zone variants",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.970"),
    publisher="Ubisoft",
    supports_claim=True,
    note=(
        "Official Y8S2 launch rules retained for Balanced and Classic where the final "
        "Red Horizon launch article says those variants remain active or unchanged."
    ),
)

RED_HORIZON_CURRENT_DZ_SOURCE = SourceEvidence(
    url=(
        "https://news.ubisoft.com/de-de/article/6PXPT3FoQS0q8BKXa6dna/"
        "the-division-2-red-horizon-cleaners-in-washington-dc-crossplay-update-"
        "dark-zone-news-and-more"
    ),
    title="The Division 2 Red Horizon: Dark Zone news",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.980"),
    publisher="Ubisoft",
    supports_claim=True,
    note="Current Red Horizon summary confirming Balanced remains unchanged.",
)

CURRENT_RAID_OVERVIEW_SOURCE = SourceEvidence(
    url=(
        "https://boostroom.com/blog/division-2-raids-explained-dark-hours-iron-horse-"
        "access-rewards-requirements"
    ),
    title="Division 2 Raids Explained: Dark Hours and Iron Horse",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.740"),
    publisher="BoostRoom",
    supports_claim=True,
    note=(
        "Published May 17, 2026; current-season corroboration for raid availability, "
        "team structure, difficulties, and rewards, not a Red Horizon mechanics authority."
    ),
)

CURRENT_RAID_ACTIVITY_SOURCE = SourceEvidence(
    url="https://www.reddit.com/r/thedivision/comments/1rq5rto/",
    title="Eight-player raids still active in 2026",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.650"),
    publisher="r/thedivision",
    supports_claim=True,
    note=(
        "March 2026 player reports corroborate active Dark Hours and Iron Horse runs and "
        "current Razorback generator/drone-control roles."
    ),
)

DARK_HOURS_MECHANICS_SOURCE = SourceEvidence(
    url="https://www.s-i-n.co.uk/div2/darkhours/",
    title="Operation Dark Hours encounter guide",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.700"),
    publisher="SIN",
    supports_claim=True,
    note=(
        "Detailed intended-mechanics reference. Re-audited for Red Horizon on August 31, "
        "2026 against the live launch notes and current raid-activity corroboration; "
        "speedrun skips and bypasses are excluded."
    ),
)

IRON_HORSE_MECHANICS_SOURCE = SourceEvidence(
    url="https://www.s-i-n.co.uk/div2/ironhorse/",
    title="Operation Iron Horse encounter guide",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.700"),
    publisher="SIN",
    supports_claim=True,
    note=(
        "Detailed intended-mechanics reference. Re-audited for Red Horizon on August 31, "
        "2026 against the live launch notes and current raid-activity corroboration; "
        "speedrun skips and bypasses are excluded."
    ),
)

CURRENT_RAID_ROLES_SOURCE = SourceEvidence(
    url="https://www.reddit.com/r/thedivision/comments/1t4ap7g/",
    title="2026 Hardcore Iron Horse role preparation",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.690"),
    publisher="r/thedivision",
    supports_claim=True,
    note=(
        "May 2026 full-raid preparation corroborating current healer, tank, DPS, and "
        "team-buff support roles."
    ),
)


def _raid_context(raid: str, encounter: int | None = None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "season": "Red Horizon",
        "mode": "raid_normal",
        "raid": raid,
        "mechanics_policy": "intended mechanics only; no skips, cheeses, bugs, or exploits",
        "red_horizon_audited_on": "2026-08-31",
    }
    if encounter is not None:
        context["encounter"] = encounter
    return context


RAID_AND_DZ_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "subject": "Operation Dark Hours",
        "entity_type": "raid",
        "claim_key": "red_horizon_overview_and_roles",
        "content": {
            "location": "Washington National Airport",
            "team_size": 8,
            "subgroups": 2,
            "encounters_in_order": [
                "Max 'Boomer' Bailey",
                "Ben 'Dizzy' Carter, Carl 'Ricochet' Dawson, and Oliver 'Weasel' Gordon",
                "Buddy and Lucy",
                "DDP-52 Razorback",
            ],
            "difficulty_profile": "damage- and communication-heavy",
            "general_roles": {
                "raid_lead_and_calls": "Controls synchronized calls and damage holds.",
                "dps": "Kills adds, weak points, and bosses during legal damage windows.",
                "boomer_kite_and_turret": "Maintains eye aggro and routes Boomer between turrets.",
                "laptop_operators": "Read and press the called defense-system laptops.",
                "gas_callers": "Coordinate matching A/B plane panels and gas swaps.",
                "buddy_lucy_callers": "Hold or resume damage to keep both armor bars in range.",
                "generator_agents": "Synchronize and hold Razorback generator circles.",
                "corner_add_control": "Own a corner, protect its generator, and stop its heavy.",
                "drone_killer": "Uses Jammer Pulse timing to control Razorback's drone waves.",
                "crossbow_or_grenade_operators": "Open vents and place explosives in legal windows.",
                "future_support": (
                    "A Future Initiative support/healer, including a red-core Future support "
                    "variant when the group uses one, buffs team damage and stabilizes chip damage."
                ),
            },
            "first_clear_guidance": (
                "Assign every player a named responsibility before each pull; do not rely on "
                "Negotiator's Dilemma bypasses or other encounter skips."
            ),
        },
        "context": _raid_context("Operation Dark Hours"),
        "confidence": 0.90,
        "sources": (
            CURRENT_RAID_OVERVIEW_SOURCE,
            CURRENT_RAID_ACTIVITY_SOURCE,
            DARK_HOURS_MECHANICS_SOURCE,
            CURRENT_RAID_ROLES_SOURCE,
        ),
    },
    {
        "subject": "Dark Hours: Max 'Boomer' Bailey",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Disable Boomer's immunity and defeat him before both turrets are lost.",
            "sequence": [
                "Destroy active defense nodes; enemies inside a node radius are immune.",
                "The eye-marked kite keeps Boomer's back toward the active mounted turret.",
                "A turret operator shoots Boomer's backpack to force a short kneeling damage window.",
                "The team damages Boomer while down; he rises after roughly two armor bars or the window expires.",
                "Shoot the chest healing unit before or while its light is green so he cannot regenerate.",
                "When the alarm sounds, central screens identify the laptop that must be pressed before nodes return.",
                "Move to the other turret after EMP/disruption and repeat.",
            ],
            "wipe_or_failure_pressure": [
                "Wrong or late laptop input restores defense nodes.",
                "Boomer destroys the first turret at about 4:30 and the second at about 9:00.",
            ],
            "recommended_roles": [
                "1-2 kite/turret operators",
                "2 laptop operators with backups",
                "4-5 DPS/add-control agents",
                "raid lead/caller",
            ],
        },
        "context": _raid_context("Operation Dark Hours", 1),
        "confidence": 0.90,
        "sources": (DARK_HOURS_MECHANICS_SOURCE, CURRENT_RAID_ACTIVITY_SOURCE),
    },
    {
        "subject": "Dark Hours: Dizzy, Ricochet, and Weasel",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Manage the two plane sides and gas states, then defeat all three bosses.",
            "sequence": [
                "Split between plane sides A and B; Dizzy starts on A and Ricochet on B.",
                "A begins under purple damage-reduction gas; B begins under orange damage-amplifying gas.",
                "Call front, middle, or back and press the matching panel on both sides simultaneously to swap gases.",
                "Swap before prolonged exposure becomes lethal/disorienting; teams commonly call around 12 stacks.",
                "Balance the first two bosses so the surviving side is prepared when the center plane lifts.",
                "Killing Dizzy or Ricochet releases Weasel on the remaining boss's side and automatically cycles gas.",
                "Reposition for orange-gas damage and finish the remaining bosses while continuing gas control.",
            ],
            "recommended_roles": [
                "two four-agent side teams",
                "one panel/gas caller per side",
                "DPS/add control on each side",
                "raid lead controlling boss timing",
            ],
        },
        "context": _raid_context("Operation Dark Hours", 2),
        "confidence": 0.90,
        "sources": (DARK_HOURS_MECHANICS_SOURCE,),
    },
    {
        "subject": "Dark Hours: Buddy and Lucy",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Defeat both Warhounds while keeping their armor bars inside the shared window.",
            "sequence": [
                "Separate Buddy and Lucy so Buddy cannot freely sustain both dogs.",
                "Assign split damage teams and one caller who orders damage or holds on each target.",
                "Keep both armor bars within the shrinking white overcharge window.",
                "When Lucy kneels and spins her 360-degree gun, stop exposing and use solid cover.",
                "When Buddy kneels, prepare for seekers/hazard and his subsequent healing cycle.",
                "If massive overcharge begins, interact with the dog-linked laptops to cancel it.",
                "Bring both dogs low and finish them close together before the encounter timer expires.",
            ],
            "timer": "Approximately 6:30 on the referenced Normal strategy.",
            "recommended_roles": [
                "Buddy damage team",
                "Lucy damage team",
                "single health-bar caller",
                "support/healer as the group's strategy requires",
            ],
        },
        "context": _raid_context("Operation Dark Hours", 3),
        "confidence": 0.90,
        "sources": (DARK_HOURS_MECHANICS_SOURCE,),
    },
    {
        "subject": "Dark Hours: DDP-52 Razorback",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Open and destroy Razorback through synchronized generator cycles, then stop the final launch.",
            "sequence": [
                "Assign two agents to each numbered corner: generator/weak-point duty and add control.",
                "Enter all four generator circles together and remain until every circle reaches 100% and turns green.",
                "Destroy the front vents from corners 1/4 and rear vents from 2/3; place a grenade or grenade-launcher round into each flashing opening so it turns green.",
                "When Razorback extends, destroy the appropriate front wings or rear panels, then damage the exposed circuits/core in the agreed order.",
                "A drone killer times Jammer Pulse for drone waves; every corner continues add and Warhound control.",
                "At roughly 90-second intervals, kill the heavy before it reaches a corner SAM console; two heavies can spawn after about half total damage.",
                "Repeat generator and damage cycles until Razorback is destroyed.",
                "Return in pairs to all four corner consoles and destroy each console when it flashes to stop the final wipe.",
            ],
            "recommended_roles": [
                "4 synchronized generator agents",
                "4 corner add-control agents",
                "1 drone killer (can also own a generator)",
                "front/rear crossbow or grenade operators",
                "heavy/SAM callers and backups",
                "Future support/healer if used by the team",
            ],
        },
        "context": _raid_context("Operation Dark Hours", 4),
        "confidence": 0.91,
        "sources": (
            DARK_HOURS_MECHANICS_SOURCE,
            CURRENT_RAID_ACTIVITY_SOURCE,
        ),
    },
    {
        "subject": "Operation Iron Horse",
        "entity_type": "raid",
        "claim_key": "red_horizon_overview_and_roles",
        "content": {
            "location": "United Ironworks",
            "team_size": 8,
            "subgroups": 2,
            "encounters_in_order": [
                "Lieutenant Gray",
                "Captain Fieser",
                "Lieutenant Williams",
                "Colonel Morozova and the Iron Horse",
            ],
            "difficulty_profile": "mechanic- and role-execution-heavy",
            "general_roles": {
                "raid_lead_and_calls": "Coordinates phase gates, diagnostics, pressure, keys, rockets, and shelter calls.",
                "dps_and_add_control": "Owns sectors/flanks, targets weak points, and burns bosses only on call.",
                "future_healer": "Sustains the raid and can provide Future Initiative damage support.",
                "red_future_support": (
                    "A damage-oriented Future Initiative support variant can contribute team "
                    "amplification where healing demand permits; it is not a substitute for the "
                    "dedicated healer in high-damage phases."
                ),
                "hazard_tank": "Handles furnace/airlock exposure, boss aggro, and protected interactions.",
                "control_room": "Reads symbols, operates doors/crucible/water, and survives isolation.",
                "diagnostics_and_furnace": "Runs top diagnostics and coordinates floor mechanics.",
                "rpg_operators": "Collect and place limited rockets on train weapons and turrets.",
                "key_tank_or_key_runner": "Collects override keys and completes auto-cannon interactions.",
                "morozova_stagger": "Times legal explosive staggers against Reckoning volleys.",
            },
        },
        "context": _raid_context("Operation Iron Horse"),
        "confidence": 0.90,
        "sources": (
            CURRENT_RAID_OVERVIEW_SOURCE,
            IRON_HORSE_MECHANICS_SOURCE,
            CURRENT_RAID_ROLES_SOURCE,
        ),
    },
    {
        "subject": "Iron Horse: Lieutenant Gray",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Break Gray's protection and defeat him to enter the foundry.",
            "sequence": [
                "Gray deploys three shield-bearing bodyguards that reduce damage reaching him.",
                "Kill or force the bodyguards out of formation to expose Gray.",
                "When Gray begins overhealing himself and the guards, shoot his backpack to interrupt it.",
                "Control adds and focus Gray once his guard formation breaks.",
            ],
            "recommended_roles": ["5-6 DPS/add control", "1 healer/support", "raid lead/caller"],
        },
        "context": _raid_context("Operation Iron Horse", 1),
        "confidence": 0.90,
        "sources": (IRON_HORSE_MECHANICS_SOURCE,),
    },
    {
        "subject": "Iron Horse: Captain Fieser",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Use codes, molten steel, and water to destroy the train weapon, then defeat Fieser.",
            "sequence": [
                "Place a self-sustaining control-room operator upstairs, control-room guards outside, sector DPS at A/B/C, and a tank/code reader for the sandforge.",
                "Read the partial code above door B; control identifies the matching full-code screen and calls its crucible symbol.",
                "Sector agents find that symbol's Wi-Fi box and shoot its red fuse. Repeat until the crucible reaches 100%; symbols refresh after every correct fuse.",
                "Control moves the crucible; agents shoot all three brakes only after movement begins, then control tips molten steel onto the train weapon.",
                "Open the correct 15/25 pressure valves around A/B/C and have control lock water at 80-85; reaching 99 resets pressure.",
                "Control opens an airlock so one or two protected agents can use the water cannons on the molten weapon until it breaks.",
                "Regroup at an airlock and damage Fieser through the opening until defeated.",
            ],
            "failure_mechanics": [
                "Firestorm kills agents left in the sandforge; shelter in an airlock or interrupt Fieser's backpack.",
                "The train-turret siren requires two RPG hits on the weapon or the control room is destroyed and the raid wipes.",
                "If Fieser lacks aggro in the forge, he can break control-room glass and lock the operator in heat/gas.",
                "Veteran/heavy waves can cut control-room power; both exterior electrical switches restore it.",
            ],
            "recommended_roles": [
                "1 control-room healer/operator",
                "2 control-room guards",
                "1 hazard tank/code reader/water-cannon operator",
                "sector DPS at A, B, and C",
                "RPG collectors with backups",
            ],
        },
        "context": _raid_context("Operation Iron Horse", 2),
        "confidence": 0.91,
        "sources": (IRON_HORSE_MECHANICS_SOURCE,),
    },
    {
        "subject": "Iron Horse: Lieutenant Williams",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Control furnace pressure, complete diagnostics and molten-steel stages, kill Williams, and execute emergency shutdown.",
            "sequence": [
                "Run top diagnostics for electrical/yellow, pressure/blue, and fire/red faults in the randomized order.",
                "Agents repair three matching electrical panels, pressure valves, or fire-valve access points; reset at the ground console after each diagnosis.",
                "Everyone leaves the top and middle levels before a reset, because the reset purge is lethal there.",
                "Damage Williams by two armor bars during each eligible appearance, then return to mechanics.",
                "Coordinate the paired cog valves so all six cogs align, destroy the orange lock lights, and shoot each exposed molten-steel plug from a safe angle. Complete all three gates.",
                "A top reader calls the eight required A-P valve changes; a ground runner shoots each valve to tighten/add or loosen/remove pressure as called.",
                "Destroy Williams's three outer-ring turrets with RPGs or weak-point damage, then kill him before the stabilized-pressure timer expires.",
                "Take his master key to the top emergency console and reset all three consoles within 30 seconds.",
            ],
            "failure_mechanics": [
                "Maximum furnace pressure wipes the raid.",
                "Reset purge kills anyone remaining on top/middle floors.",
                "Molten-steel release kills agents standing directly behind it.",
                "Williams's poison attacks health directly; foam mines require self/teammate shots at the trapped agent's feet.",
                "His backpack heals him and must be destroyed or disrupted.",
            ],
            "recommended_roles": [
                "1 top diagnostics reader",
                "1 command-station/reset tank",
                "1 full healer",
                "1 cog/valve runner",
                "DPS/add/sniper control",
                "RPG/turret operators",
                "emergency-console assignments",
            ],
        },
        "context": _raid_context("Operation Iron Horse", 3),
        "confidence": 0.91,
        "sources": (IRON_HORSE_MECHANICS_SOURCE, CURRENT_RAID_ROLES_SOURCE),
    },
    {
        "subject": "Iron Horse: Colonel Morozova and Iron Horse",
        "entity_type": "raid_encounter",
        "claim_key": "intended_progression_mechanics",
        "content": {
            "objective": "Disable the train's weapons phase by phase, survive Morozova's airstrikes, then defeat both targets.",
            "core_mechanics": [
                "Two RPG enemies spawn on opposite flanks; collect every launcher for the red shell and weapon objectives.",
                "Each phase's red shell needs six RPG hits before Earthshaker fires.",
                "Kill foam heavies for override keys; a key runner charges the auto-cannon circle and uses the key on the pre-fire call.",
                "Use legal explosive damage to stagger Morozova and interrupt Reckoning volleys without over-damaging her before the phase call.",
                "Clear shock harpoons beneath the bridge, then shelter behind the bridge cover inside the marked safe limits for each airstrike.",
            ],
            "phases": [
                "Phase 1: stop the red shell; use four key overrides to expose/temporarily disable all four mortars; spawn Morozova and shelter from the airstrike.",
                "Phase 2: stop the red shell; remove three armor bars from Morozova; shelter.",
                "Phase 3: repeat shell and three-bar Morozova damage; the Iron Horse health bar appears; shelter.",
                "Phase 4: stop the shell; use three keys to permanently destroy mortar pairs and reduce Iron Horse to 1%; strip Morozova's remaining armor; shelter.",
                "Phase 5: kill Morozova, then rapidly place the final RPG on the newly loading red shell to finish Iron Horse.",
            ],
            "recommended_roles": [
                "1 Vanguard/key tank and Morozova control",
                "1 Future Initiative healer/support",
                "2 left-flank DPS including an RPG operator",
                "2 right-flank DPS including an RPG operator",
                "sniper/add control and rocket backups",
                "raid lead for shell, key, damage-stop, harpoon, and bridge calls",
            ],
        },
        "context": _raid_context("Operation Iron Horse", 4),
        "confidence": 0.91,
        "sources": (IRON_HORSE_MECHANICS_SOURCE, CURRENT_RAID_ROLES_SOURCE),
    },
    {
        "subject": "Red Horizon Toxic Dark Zone",
        "entity_type": "dark_zone_variant",
        "claim_key": "current_mechanics_and_build_principles",
        "content": {
            "focus": "Permanent PvE Dark Zone",
            "player_damage": False,
            "rogue_protocol": False,
            "normalization": "Active; players and gear scale to level 40.",
            "shd_and_expertise": "Active within the normalized ruleset.",
            "combat_rules": "PvE values apply to talents, Gear Sets, Skills, and weapons against NPCs; Prototype Gear remains normalized.",
            "factions": "Multiple factions can appear, including Black Tusk.",
            "toxicity": "Builds over time; extracting gear now clears it.",
            "removed_red_horizon_mechanics": ["Sample Canisters", "Surge"],
            "reward": "Landmark chests have a 20% chance to drop a contaminated cache from the special DZ pool.",
            "build_templates": {
                "solo_sustain": {
                    "purpose": "Long landmark loops with limited downtime.",
                    "priorities": [
                        "reliable PvE damage without short PvP-only burst windows",
                        "armor regeneration or armor-on-kill",
                        "Protection from Elites for elite-heavy landmarks",
                        "hazard/status protection when the current faction mix warrants it",
                        "ammo sustain and a revive or crowd-control fallback",
                    ],
                    "avoid": "Do not import a PvP sheet blindly; PvE talent and Skill behavior applies here.",
                },
                "group_support": {
                    "purpose": "Four-agent landmark clears and safer extractions.",
                    "priorities": [
                        "one damage-support or healer slot",
                        "three complementary damage/control slots",
                        "shared crowd control and anti-elite coverage",
                    ],
                },
            },
        },
        "context": {"season": "Red Horizon", "mode": "toxic_dark_zone"},
        "confidence": 0.99,
        "sources": (RED_HORIZON_FINAL_SOURCE,),
    },
    {
        "subject": "Red Horizon Balanced Dark Zone",
        "entity_type": "dark_zone_variant",
        "claim_key": "current_mechanics_and_build_principles",
        "content": {
            "focus": "Competitive, normalized PvEvP",
            "rogue_protocol": True,
            "normalization": "High-level normalization based on Conflict rules.",
            "shd_and_expertise": False,
            "global_pvp_balance": True,
            "red_horizon_status": "Unchanged and active every week.",
            "build_template": {
                "purpose": "Low-progression-dependency PvP and extraction play.",
                "priorities": [
                    "test the normalized PvP sheet in the Shooting Range",
                    "balance burst damage, survivability, and status resistance",
                    "favor internally complete talent/attribute synergy over Expertise investment",
                    "carry an escape or recovery option for extraction pressure",
                ],
                "warning": "SHD Watch and Expertise bonuses are disabled; Global PvP overrides still apply.",
            },
        },
        "context": {"season": "Red Horizon", "mode": "balanced_dark_zone"},
        "confidence": 0.98,
        "sources": (INTO_THE_DARK_SOURCE, RED_HORIZON_CURRENT_DZ_SOURCE),
    },
    {
        "subject": "Red Horizon Classic Dark Zone",
        "entity_type": "dark_zone_variant",
        "claim_key": "current_mechanics_and_build_principles",
        "content": {
            "focus": "Baseline PvEvP risk-versus-reward",
            "rogue_protocol": True,
            "normalization": True,
            "shd_and_expertise": True,
            "global_pvp_balance": True,
            "invasions": "Periodic invasions remain part of Classic.",
            "rotation": "Alternates weekly with Blackout while Toxic and Balanced remain present.",
            "build_template": {
                "purpose": "Flexible landmark, rogue-defense, and extraction play.",
                "priorities": [
                    "verify the normalized PvP stat sheet rather than trusting open-world values",
                    "combine sustained NPC clearing with player burst/pressure",
                    "retain enough armor, recovery, or disengage tools to survive third parties",
                    "use current PvP talent/Gear Set/Skill overrides",
                ],
            },
        },
        "context": {"season": "Red Horizon", "mode": "classic_dark_zone"},
        "confidence": 0.98,
        "sources": (INTO_THE_DARK_SOURCE,),
    },
    {
        "subject": "Red Horizon Invaded Dark Zone",
        "entity_type": "dark_zone_state",
        "claim_key": "current_meaning_and_build_principles",
        "content": {
            "meaning": (
                "Invaded is an enemy/state modifier, not a single universal normalization "
                "ruleset. Classic supports periodic invasions; Blackout is permanently Invaded."
            ),
            "enemy_faction": "Black Tusk",
            "normalization_rule": (
                "Read the active variant: Classic remains normalized, while Blackout is "
                "non-normalized and uncapped."
            ),
            "build_priorities": [
                "Black Tusk weak-point and robotics control",
                "EMP/disruption or fast Warhound/drone removal where useful",
                "a PvP-capable damage/defense core because Rogue Protocol remains active in PvP variants",
                "variant-correct stat testing before entry",
            ],
        },
        "context": {"season": "Red Horizon", "mode": "invaded_dark_zone"},
        "confidence": 0.98,
        "sources": (INTO_THE_DARK_SOURCE,),
    },
    {
        "subject": "Red Horizon Blackout Dark Zone",
        "entity_type": "dark_zone_variant",
        "claim_key": "current_mechanics_and_build_principles",
        "content": {
            "focus": "Fully uncapped PvEvP",
            "rogue_protocol": True,
            "normalization": False,
            "shd_and_expertise": True,
            "global_pvp_balance": True,
            "invasion": "Permanent; Black Tusk is the main faction and higher-rank enemies are tougher.",
            "prototype_rule": "Full base stats apply; Augments still use PvP-balanced values.",
            "loot": "Heroic-quality; 20% chance for an additional contaminated special-pool item.",
            "build_templates": {
                "max_progression_pressure": {
                    "purpose": "Exploit legal account progression without losing PvP viability.",
                    "priorities": [
                        "fully optimized cores and attributes",
                        "relevant Expertise on the active weapons and survivability-critical gear",
                        "full SHD Watch contribution",
                        "current PvP talent/Gear Set/Skill values",
                        "anti-Black-Tusk utility without sacrificing rogue defense",
                    ],
                },
                "prototype_hybrid": {
                    "purpose": "Use uncapped Prototype base stats in a coherent build.",
                    "priorities": [
                        "evaluate base attributes at full strength",
                        "evaluate Augments using PvP-balanced values",
                        "do not assume an open-world augment tooltip is the Blackout PvP result",
                    ],
                },
            },
        },
        "context": {"season": "Red Horizon", "mode": "blackout_dark_zone"},
        "confidence": 0.99,
        "sources": (RED_HORIZON_FINAL_SOURCE,),
    },
)
