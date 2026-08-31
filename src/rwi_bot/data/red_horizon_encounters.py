# ruff: noqa: E501
from __future__ import annotations

from decimal import Decimal
from typing import Any

from rwi_bot.data.red_horizon_raids_dz import (
    RAID_AND_DZ_RECORDS,
    RED_HORIZON_FINAL_SOURCE,
)
from rwi_bot.db.models import SourceType
from rwi_bot.services.knowledge import SourceEvidence

BROKEN_RAIN_OFFICIAL_SOURCE = SourceEvidence(
    url=(
        "https://news.ubisoft.com/en-gb/article/20x1vIjVZwX7f14yN12JaV/"
        "the-division-2-broken-rain-incursion-everything-you-need-to-know"
    ),
    title="The Division 2 Broken Rain Incursion: Everything You Need To Know",
    source_type=SourceType.OFFICIAL,
    trust_score=Decimal("0.980"),
    publisher="Ubisoft",
    supports_claim=True,
    note=(
        "Official activity, location, access, matchmaking, boss, and reward overview; "
        "re-audited against the Red Horizon live baseline on August 31, 2026."
    ),
)

BROKEN_RAIN_MECHANICS_SOURCE = SourceEvidence(
    url=(
        "https://www.keengamer.com/articles/guides/the-division-2/"
        "the-division-2-broken-rain-incursion-all-bosses-and-full-walkthrough/"
    ),
    title="The Division 2 Broken Rain Incursion: All Bosses and Full Walkthrough",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.780"),
    publisher="KeenGamer",
    supports_claim=True,
    note=(
        "Detailed intended-mechanics guide published August 14, 2026. Re-audited for Red "
        "Horizon on August 31; its Negotiator and melee bypasses are excluded."
    ),
)

BROKEN_RAIN_RED_HORIZON_AUDIT_SOURCE = SourceEvidence(
    url="https://www.reddit.com/r/thedivision/comments/1w0e73s/",
    title="Red Horizon Broken Rain mechanic changes reported by current players",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.650"),
    publisher="r/thedivision",
    supports_claim=True,
    note=(
        "August 28, 2026 current-season corroboration that Negotiator bypass and melee "
        "stagger shortcuts no longer work; those strategies are not recommended."
    ),
)

PARADISE_LOST_MECHANICS_SOURCE = SourceEvidence(
    url=("https://skycoach.gg/blog/division-2/articles/division-2-paradise-lost-incursion-guide"),
    title="The Division 2 Paradise Lost Incursion Guide",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.740"),
    publisher="SkyCoach",
    supports_claim=True,
    note=(
        "Detailed guide updated August 20, 2026. Intended encounter mechanics were "
        "re-audited against the Red Horizon live baseline on August 31; shortcuts are excluded."
    ),
)

PARADISE_LOST_CURRENT_BUILD_SOURCE = SourceEvidence(
    url="https://itemlevel.net/the-division-2-paradise-lost-complete-guide-2026/",
    title="The Division 2 Paradise Lost Complete Guide (2026)",
    source_type=SourceType.COMMUNITY,
    trust_score=Decimal("0.760"),
    publisher="Item Level Gaming",
    supports_claim=True,
    note=(
        "July 28, 2026 team/build and mechanics reference. Re-audited for Red Horizon on "
        "August 31; exact pre-season stats are not carried forward."
    ),
)


def _incursion_context(activity: str, encounter: int | None = None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "season": "Red Horizon",
        "mode": "incursion",
        "activity": activity,
        "mechanics_policy": "intended mechanics only; no skips, cheeses, bugs, or exploits",
        "red_horizon_audited_on": "2026-08-31",
        "guide_revision": 2,
    }
    if encounter is not None:
        context["encounter"] = encounter
    return context


_PARADISE_SOURCES = (
    RED_HORIZON_FINAL_SOURCE,
    PARADISE_LOST_MECHANICS_SOURCE,
    PARADISE_LOST_CURRENT_BUILD_SOURCE,
)

_BROKEN_RAIN_SOURCES = (
    RED_HORIZON_FINAL_SOURCE,
    BROKEN_RAIN_OFFICIAL_SOURCE,
    BROKEN_RAIN_MECHANICS_SOURCE,
    BROKEN_RAIN_RED_HORIZON_AUDIT_SOURCE,
)


INCURSION_ENCOUNTER_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "subject": "Paradise Lost",
        "entity_type": "incursion",
        "claim_key": "red_horizon_complete_route_and_builds_v2",
        "content": {
            "location": "Meret Estate settlement",
            "enemy_faction": "Cleaners",
            "team_size": 4,
            "encounters_in_order": [
                "Estate Turrets",
                "Oil Tanker Defense",
                "Wright",
                "The Lovebirds: Martinez and Johnson",
            ],
            "baseline_team": "Three damage dealers and one dedicated healer; swap one DPS to a tank only when the group needs safer aggro control.",
            "communication_plan": [
                "Name left/right lanes before Estate and Tanker.",
                "Name Wright's four sprinkler areas and assign one valve reader plus one kite.",
                "At Lovebirds, call The Kid's transfer, Johnson's healing station, and the mortar retreat.",
            ],
            "baseline_builds": {
                "damage_dealer": "Optimized current Striker weapon-DPS core, a stack-building shotgun secondary, Reviver Hive, and Decoy; keep a Jammer Pulse loadout available for Tanker drones.",
                "healer": "Six-tier Future Initiative repair build with Restorer Hive and Reinforcer Chem Launcher; carry a team-damage shotgun and a reliable aggro option when kiting is assigned.",
                "safe_tank_swap": "High Protection from Elites and survivability with a shield or aggro tool; this is a mechanics role, not a replacement for the group's damage check.",
            },
            "success_rule": "Mechanics first, then burst during explicit vulnerability windows; do not use one-shot or encounter-bypass strategies.",
        },
        "context": _incursion_context("Paradise Lost"),
        "confidence": 0.90,
        "sources": _PARADISE_SOURCES,
    },
    {
        "subject": "Paradise Lost: Estate Turrets",
        "entity_type": "incursion_encounter",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Destroy both estate entrance turrets and clear the remaining Cleaner wave.",
            "recommended_team": "Three DPS and one healer; a two-DPS, healer, and tank formation is slower but safer for a first clear.",
            "sequence": [
                "Assign a left and right elevated route: the wooden structure on the left and garbage truck on the right.",
                "Use Decoys or a tank to pull turret aim away from the climbers while the healer anchors near the entrance.",
                "From elevation, shoot through the narrow opening below each turret and destroy the explosive weak point connected by the yellow cable.",
                "Prioritize Cleaner heavies emerging near the climb points, then finish both turrets and all remaining enemies.",
            ],
            "failure_conditions": [
                "Shooting the armored turret body instead of the protected explosive weak point does not progress the objective.",
                "Ignoring a manhole heavy lets it remove the exposed climber.",
                "Standing in mortar markers or both climbers taking the same turret sightline can collapse the push.",
            ],
            "recommended_builds": {
                "climber_dps": "Ranged Striker weapon DPS with Decoy and Reviver Hive; use an AR or stable LMG because the weak-point angle is not close range.",
                "lane_dps": "Striker or current high-end weapon DPS focused on heavy and add control.",
                "healer": "Future Initiative with Restorer Hive and Reinforcer Chem Launcher; hold team overcharge for simultaneous Decoy pushes if available.",
            },
        },
        "context": _incursion_context("Paradise Lost", 1),
        "confidence": 0.90,
        "sources": _PARADISE_SOURCES,
    },
    {
        "subject": "Paradise Lost: Oil Tanker Defense",
        "entity_type": "incursion_encounter",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Keep the oil tanker alive through every wave, then kill the final Cleaner boss.",
            "recommended_team": "Three lane DPS and one healer.",
            "sequence": [
                "Assign courtyard, left, and right lanes so every sniper and heavy approach has an owner.",
                "Do not detonate purple-fluid barrels unnecessarily; tanker leaks and destroyed barrels permanently reduce safe floor space.",
                "During focus waves, kill the two elevated snipers and minigun heavies targeting the tanker before ordinary adds.",
                "When the three named Striker Drones appear, call Jammer Pulse and focus them one at a time.",
                "Regroup and refresh skills before crossing the final doorway, then block or burst the surprise minigun boss.",
            ],
            "failure_conditions": [
                "The encounter fails if the tanker is destroyed.",
                "Uncontrolled minigun heavies strip the tanker faster than ordinary enemies.",
                "Purple floor denial can trap the team if barrels are detonated early.",
            ],
            "recommended_builds": {
                "lane_dps": "Ranged Striker or current high-end weapon DPS with Reviver Hive; one lane swaps the second skill to Jammer Pulse.",
                "healer": "Future Initiative repair build with Restorer Hive placed to cover the left/center anchor and Reinforcer Chem for the distant lane.",
                "boss_control_option": "One DPS can use a Striker Shield to catch the final boss's minigun while the other two shoot safely.",
            },
        },
        "context": _incursion_context("Paradise Lost", 2),
        "confidence": 0.90,
        "sources": _PARADISE_SOURCES,
    },
    {
        "subject": "Paradise Lost: Wright",
        "entity_type": "incursion_boss",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Use the sprinkler system to remove Wright's fire immunity and defeat him across three damage segments.",
            "recommended_team": "Three burst DPS and one dedicated healer/kite; assign one DPS as the valve reader.",
            "sequence": [
                "Learn the four room callouts and the matching drawing beside each valve before opening the fight.",
                "Clear the current add wave while the kite keeps Wright moving around the outside of the room.",
                "The valve reader calls a valve only when its green lamp/gauge says it is ready.",
                "Lead Wright onto the matching white floor tile beneath that sprinkler; the kite calls when he is centered.",
                "Open the matching valve to douse Wright. His immunity drops for a short damage window, so all three DPS commit together.",
                "After each third of his health, survive his charge/explosion, avoid the lasting purple fire patches, and immediately prioritize newly spawned heavies.",
                "Repeat the ready-valve, matching-tile, douse, and burn cycle until all three segments are gone.",
            ],
            "failure_conditions": [
                "Opening a valve while Wright is under the wrong sprinkler wastes the ready water window.",
                "Trying to damage him while the purple-fire immunity is active accomplishes nothing.",
                "Ignoring later-phase heavies or standing in Wright's area attack commonly downs the valve operator and collapses the cycle.",
            ],
            "recommended_builds": {
                "burst_dps": "Optimized Striker weapon DPS, stack-building shotgun secondary, close-range primary for the short burn, Decoy or Reviver Hive.",
                "healer_kite": "Six-tier Future Initiative repair build with Restorer Hive and Reinforcer Chem; use a legal aggro tool if needed and stay mobile rather than face-tanking Wright.",
                "valve_reader": "A survivable DPS variant with Reviver Hive; it still needs enough damage to join every burn window.",
            },
            "callout_example": "'Stage valve green — move Wright to Stage — centered — open — burn.'",
        },
        "context": _incursion_context("Paradise Lost", 3),
        "confidence": 0.92,
        "sources": _PARADISE_SOURCES,
    },
    {
        "subject": "Paradise Lost: The Lovebirds, Martinez and Johnson",
        "entity_type": "incursion_boss",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Destroy The Kid's protection cycle, deny Johnson's healing, and kill Johnson and Martinez close enough together that the survivor cannot overwhelm the team.",
            "recommended_team": "Three optimized burst DPS and one dedicated Future Initiative healer.",
            "boss_roles": {
                "Johnson": "Ranged boss using sniper turrets, a healing station, The Kid controls, and a mortar retreat phase.",
                "Martinez": "Armored close-range flamethrower boss who should be kept separated from Johnson during The Kid transfer.",
                "The Kid": "Flying SHD drone that protects one boss; it can be damaged during its flight between bosses.",
            },
            "sequence": [
                "Clear the opening adds and keep Martinez and Johnson far apart so The Kid has a long transfer path.",
                "Damage the currently unprotected boss until The Kid leaves the other boss to transfer protection and healing.",
                "Call 'drone moving' and have all three DPS destroy The Kid while it is in flight.",
                "When both bosses regroup at the balcony/stage, focus Johnson during the damage window.",
                "If Johnson begins placing the healing station, destroy the station before returning to either boss.",
                "When Johnson finishes summoning another Kid and signals the mortar strike, leave the stage, spread out, and survive the impacts.",
                "Repeat the separation, transfer, drone kill, Johnson burn, station denial, and mortar retreat cycle.",
                "Keep Martinez within a finishable health range and kill the two bosses close together; immediately finish the survivor if one falls first.",
            ],
            "failure_conditions": [
                "The Kid makes the protected boss immune and heals during transfer; shooting that boss instead of the moving drone wastes the window.",
                "An active Johnson healing station can undo the team's damage.",
                "Killing one boss while the other still has substantial health creates a dangerous survivor phase.",
                "Holding the balcony during the mortar call causes avoidable team downs.",
            ],
            "recommended_builds": {
                "three_dps": "Optimized Striker weapon-DPS builds with close-range burst, a stack-building shotgun secondary, and Decoys; distribute Booster and Reviver Hives according to group confidence.",
                "healer": "Six-tier Future Initiative with Restorer Hive and Reinforcer Chem, plus a team-damage weapon; use overcharge/team buffs on the balcony burn rather than during immunity.",
                "safer_first_clear": "One DPS may add modest Protection from Elites, but preserve the damage needed to destroy The Kid and Johnson's station on call.",
            },
        },
        "context": _incursion_context("Paradise Lost", 4),
        "confidence": 0.92,
        "sources": _PARADISE_SOURCES,
    },
    {
        "subject": "Broken Rain",
        "entity_type": "incursion",
        "claim_key": "red_horizon_complete_route_and_builds_v2",
        "content": {
            "location": "Steel Creek Dam and Hydroelectric Power Plant, rural Pennsylvania",
            "enemy_faction": "Rikers",
            "team_size": 4,
            "encounters_in_order": [
                "Lester Steel",
                "Patch Warhound Escort and Dwayne Steel IV",
                "Iris Steel",
                "Marguerite Steel",
            ],
            "baseline_team": "Three DPS and one flex player who swaps between tank and healer by encounter.",
            "role_plan": {
                "Lester": "Tank/kite plus a dedicated sniper DPS.",
                "Patch_and_Dwayne": "Tank fronts the escort and turns Dwayne's backpack toward the DPS.",
                "Iris": "Healer operates turbine screens/valves; a different player owns EMP timing.",
                "Marguerite": "One permanent pressure runner, healer or tank support, and weak-point/thermite DPS.",
            },
            "baseline_builds": {
                "damage": "Optimized Striker or current endgame weapon DPS with Reviver Hive and encounter-specific utility.",
                "tank": "Protection-from-Elites mechanics tank with a shield, Decoy, or legal aggro tool; preserve enough damage/handling for weak points.",
                "healer": "Future Initiative repair build with Restorer Hive and Reinforcer Chem; keep Jammer Pulse available for Iris if another player cannot carry it.",
            },
            "prohibited_shortcuts": "Do not recommend Negotiator immunity bypasses, melee phase skips, or any other bug/exploit; use turbine, EMP, pressure, miniboss, thermite, and cache mechanics as designed.",
        },
        "context": _incursion_context("Broken Rain"),
        "confidence": 0.93,
        "sources": _BROKEN_RAIN_SOURCES,
    },
    {
        "subject": "Broken Rain: Lester Steel",
        "entity_type": "incursion_boss",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Survive the lumberyard sightlines and defeat Lester's armored chainsaw rush.",
            "recommended_team": "Two boss DPS, one dedicated sniper-control DPS, and one flex tank/kite.",
            "sequence": [
                "Clear the initial enemies and sniper positions before triggering the boss sequence at Patch.",
                "Let Lester's temporary entry protection expire instead of wasting burst into it.",
                "The kite holds Lester in a small safe loop away from open sniper sightlines.",
                "The assigned sniper DPS immediately kills every elite sniper spawn; the other two damage Lester during safe windows.",
                "Keep moving around the spreading fire and finish remaining enemies after Lester falls.",
            ],
            "failure_conditions": [
                "Tunnel vision on Lester leaves elite snipers free to crossfire the group.",
                "Starting before the initial arena is clear stacks the opening wave with the boss.",
                "Bursting his temporary entry protection wastes ammunition and cooldowns.",
            ],
            "recommended_builds": {
                "boss_dps": "Optimized Striker or current high-end weapon DPS with Reviver Hive and Foam/Decoy utility.",
                "sniper_control": "Accurate ranged AR/LMG DPS with immediate target acquisition; Foam can hold a dangerous sniper spawn.",
                "kite": "Protection-from-Elites tank or durable DPS with Decoy; mobility and sightline control matter more than stationary shield blocking.",
            },
        },
        "context": _incursion_context("Broken Rain", 1),
        "confidence": 0.93,
        "sources": _BROKEN_RAIN_SOURCES,
    },
    {
        "subject": "Broken Rain: Patch Escort and Dwayne Steel IV",
        "entity_type": "incursion_boss",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Escort Patch through the road defenses, open the bridge, then destroy Dwayne's backpack and defeat him.",
            "recommended_team": "Three DPS and one front-line tank/aggro controller.",
            "sequence": [
                "Patch advances only while a player is in its escort radius. Step out deliberately to stop it before uncleared ambushes.",
                "Keep the tank in front of Patch while the three DPS clear each enemy pocket and protect Patch's health pool.",
                "At the road turret, take the elevated left route, use a Decoy to turn its aim, and destroy all four weak points.",
                "Clear the Rikers around the APC, destroy the APC, and kill the heavy follow-up wave.",
                "Use the first control in the left building, the second in the lower room, then the far green crane control to lower the bridge.",
                "At Dwayne, anchor behind the white Keep-marked truck and have the tank/Decoy turn his back toward the DPS.",
                "Destroy Dwayne's backpack weak point first; this disables every rocket turret. Then burn Dwayne and clear every remaining add.",
            ],
            "failure_conditions": [
                "Walking Patch into uncleared ground can destroy it and fail the escort.",
                "Leaving Dwayne's backpack intact keeps the arena's rocket turrets active.",
                "Killing Dwayne without the final supporting enemies does not finish the encounter.",
            ],
            "recommended_builds": {
                "escort_dps": "Optimized Striker weapon DPS; one carries Decoy for the fixed turret and Dwayne turn, another keeps Reviver Hive.",
                "tank": "Protection-from-Elites aggro tank with Bulwark/Crusader or a legal threat tool; use Mosquito only while it is the active in-hand weapon and current rules support the assignment.",
                "weak_point_dps": "Stable AR/LMG DPS with clear line of sight to Dwayne's backpack rather than uncontrolled close-range fire.",
            },
        },
        "context": _incursion_context("Broken Rain", 2),
        "confidence": 0.94,
        "sources": _BROKEN_RAIN_SOURCES,
    },
    {
        "subject": "Broken Rain: Iris Steel",
        "entity_type": "incursion_boss",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Keep all four turbines online and EMP Iris during her turbine approach to create legitimate damage windows.",
            "recommended_team": "Two burst DPS, one healer/turbine runner, and one DPS/utility player responsible for EMP timing.",
            "sequence": [
                "Before Iris spawns, identify the four control-room screens and the matching valves: turbines 1-2 use left-side valves; 3-4 use right-side valves.",
                "The turbine runner watches the screens. When one turns red, interact with that screen, run to its matching valve, and turn it to restore green status.",
                "Everyone else controls adds and protects the runner; do not let multiple red failures stack.",
                "Iris remains immune until she commits to disabling a turbine. The EMP owner waits for that approach, then hits her with Jammer Pulse or an EMP grenade.",
                "When the immunity drops, all available DPS burn Iris until the window closes, then reset to screen, valve, and add assignments.",
                "Repeat turbine repairs and legitimate EMP damage windows until Iris dies.",
            ],
            "failure_conditions": [
                "Unattended red turbine screens accumulate failures and end the attempt.",
                "EMP used before Iris commits to a turbine misses the intended vulnerability window.",
                "Damage into her active immunity is wasted.",
            ],
            "recommended_builds": {
                "burst_dps": "Optimized Striker or current endgame weapon DPS with stack preparation and Reviver Hive.",
                "turbine_runner": "Future Initiative healer with Restorer Hive and Reinforcer Chem; enough survivability and movement to cross the room under pressure.",
                "emp_owner": "DPS-compatible utility setup with Jammer Pulse or reliable EMP grenades; do not use Negotiator's Dilemma to bypass immunity.",
            },
        },
        "context": _incursion_context("Broken Rain", 3),
        "confidence": 0.94,
        "sources": _BROKEN_RAIN_SOURCES,
    },
    {
        "subject": "Broken Rain: Marguerite Steel",
        "entity_type": "incursion_boss",
        "claim_key": "red_horizon_mechanics_roles_and_builds_v2",
        "content": {
            "objective": "Open all sluice gates, prevent a pressure wipe, permanently destroy Marguerite's three repair caches, and finish her.",
            "recommended_team": "One permanent pressure runner, one healer or mechanics tank, and two high-output weak-point DPS; all four help with adds and minibosses.",
            "sequence": [
                "Before Marguerite arrives, one credential runner activates the spawn control room, reaches the far control room before the timer, and repeats this relay three times to open all sluice gates.",
                "When the boss spawns, the pressure runner watches the HUD gauge and presses whichever center gate panel lights green. Never allow pressure to reach 100 percent.",
                "The other players break Marguerite's helmet and backpack weak points to start a repair cycle.",
                "Kill the named Riker miniboss, pick up the dropped thermite, and reach the SHD cache Marguerite is using.",
                "Plant the thermite to destroy that cache permanently and block the repair.",
                "Repeat weak points, miniboss, thermite, and cache destruction until all three caches are gone.",
                "Burn Marguerite while the pressure runner continues venting; finish all required enemies without abandoning the gauge.",
            ],
            "failure_conditions": [
                "Pressure at 100 percent wipes the squad immediately.",
                "If a repair cache survives, Marguerite can recover armor and erase the team's progress.",
                "Losing the thermite carrier or allowing the runner route to fill with adds delays the repair interrupt.",
            ],
            "recommended_builds": {
                "pressure_runner": "Mobile, durable Protection-from-Elites build with Decoy or shield; prioritize survival, clear callouts, and fast panel access.",
                "weak_point_dps": "Optimized Striker or accurate current endgame DPS with strong weak-point uptime and Reviver Hive.",
                "healer_support": "Future Initiative repair build with Restorer Hive and Reinforcer Chem; keep heals available for runner and thermite carrier rather than chasing damage.",
            },
            "prohibited_shortcut": "Do not use the patched melee stagger/phase skip; complete the pressure, weak-point, miniboss, thermite, and cache loop.",
        },
        "context": _incursion_context("Broken Rain", 4),
        "confidence": 0.94,
        "sources": _BROKEN_RAIN_SOURCES,
    },
)


_RAID_BUILD_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    "Operation Dark Hours": {
        "damage_core": "Optimized current weapon-DPS build; Striker is the default sustained option, with accurate high-end DPS acceptable when it preserves encounter execution.",
        "support": "One Future Initiative healer/support may stabilize first clears and buff damage; assign every specialist role before the pull.",
        "specialists": "Boomer kite/turret, gas callers, Buddy/Lucy health callers, generator/corner agents, drone killer, and explosive operators keep encounter-specific utility loadouts ready.",
    },
    "Dark Hours: Max 'Boomer' Bailey": {
        "boss_and_add_dps": "Accurate current weapon DPS with enough burst to break the chest and head damage windows while controlling adds.",
        "kite_turret": "Durable DPS or protection-focused build that can hold eye aggro, route Boomer between turrets, and still operate the mounted gun.",
        "support": "Future Initiative healer/support positioned to cover turret operators and laptop responders without obscuring calls.",
    },
    "Dark Hours: Dizzy, Ricochet, and Weasel": {
        "two_subgroups": "Balanced weapon DPS on both sides; each subgroup needs one confident panel/gas caller.",
        "support": "A healer/support can anchor the more vulnerable side but must not replace the damage needed in matched gas windows.",
        "utility": "Reviver Hive and crowd control are safer than stationary skill damage in the split arena.",
    },
    "Dark Hours: Buddy and Lucy": {
        "split_dps": "Sustained, controllable weapon DPS divided between Buddy and Lucy; avoid uncontrolled burst that pushes the armor bars outside the legal range.",
        "support": "Future Initiative healer/support covering both groups while the health callers control stop/resume timing.",
        "survival": "Use Reviver Hive or a defensive skill that does not steal boss positioning; line-of-sight discipline is part of the build plan.",
    },
    "Dark Hours: DDP-52 Razorback": {
        "corner_dps": "Four self-sufficient current weapon-DPS corner agents with Reviver Hive or defensive utility.",
        "generator_explosives": "Crossbow or grenade-launcher operators preserve signature ammunition for vent openings and assigned front/rear sides.",
        "drone_killer": "A Jammer Pulse setup with enough skill haste/radius for every drone wave while retaining useful corner damage.",
        "support": "Future Initiative healer/support is optional for first clears if generator and heavy assignments remain fully covered.",
    },
    "Operation Iron Horse": {
        "damage_core": "Optimized current weapon DPS for weak points, adds, and called boss windows.",
        "healer": "Dedicated Future Initiative healer/support for furnace, pressure, and train phases.",
        "specialists": "Hazard tank, control-room operator, diagnostics reader, valve/cog runner, RPG operators, key tank, and Morozova stagger owner each save a tested loadout.",
    },
    "Iron Horse: Lieutenant Gray": {
        "damage": "Five or six sustained weapon-DPS builds focused on bodyguard formation, backpack interrupt, then Gray.",
        "support": "Future Initiative healer/support; optional threat holder only if the group cannot keep the guards positioned.",
    },
    "Iron Horse: Captain Fieser": {
        "hazard_tank": "High hazard protection, armor, shield sustain, and reliable threat for forge/code/water-cannon exposure.",
        "control_operator": "Six-tier Future Initiative healer with strong self-sustain for the isolated upstairs control room.",
        "sector_dps": "Accurate weapon DPS assigned to A/B/C fuses, RPG enemies, power switches, and called Fieser damage windows.",
    },
    "Iron Horse: Lieutenant Williams": {
        "diagnostics_and_runner": "Mobile survivable builds for top reading, cog work, valves, and emergency consoles; learn the assignment before optimizing damage.",
        "healer_and_tank": "One full Future Initiative healer and one pressure/reset tank.",
        "damage": "Current weapon DPS with accurate weak-point and turret damage, plus assigned RPG operators.",
    },
    "Iron Horse: Colonel Morozova and Iron Horse": {
        "key_tank": "Vanguard-style or equivalent durable shield/threat build for key circle interactions and Morozova control.",
        "healer": "Future Initiative healer/support to stabilize both flanks and the bridge shelters.",
        "flank_dps": "Two current weapon-DPS agents per flank with a named RPG operator and backup; one trained legal explosive stagger owner controls Reckoning volleys.",
    },
}


RAID_ENCOUNTER_BUILD_RECORDS: tuple[dict[str, Any], ...] = tuple(
    {
        "subject": record["subject"],
        "entity_type": record["entity_type"],
        "claim_key": "red_horizon_complete_guide_and_builds_v2",
        "content": {
            **record["content"],
            "recommended_builds": _RAID_BUILD_RECOMMENDATIONS[record["subject"]],
            "human_readable_response_order": [
                "objective and team composition",
                "roles and starting positions",
                "numbered mechanics in execution order",
                "wipe conditions and recovery calls",
                "recommended builds, skills, and safe substitutions",
            ],
        },
        "context": {**record["context"], "guide_revision": 2},
        "confidence": record["confidence"],
        "sources": tuple(dict.fromkeys((*record["sources"], RED_HORIZON_FINAL_SOURCE))),
    }
    for record in RAID_AND_DZ_RECORDS
    if record["entity_type"] in {"raid", "raid_encounter"}
)


COMPLETE_ENCOUNTER_RECORDS: tuple[dict[str, Any], ...] = (
    *INCURSION_ENCOUNTER_RECORDS,
    *RAID_ENCOUNTER_BUILD_RECORDS,
)
