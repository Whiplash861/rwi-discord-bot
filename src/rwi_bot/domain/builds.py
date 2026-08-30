from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import islice, product
from math import prod


class BuildLegality(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    INCOMPLETE = "incomplete"


class BuildMode(StrEnum):
    PVE = "pve"
    PVP = "pvp"


class EquipmentKind(StrEnum):
    GEAR = "gear"
    WEAPON = "weapon"
    SKILL = "skill"
    MOD = "mod"


OPTIMIZATION_PRIORITIES = frozenset(
    {
        "armor",
        "armor_regen",
        "hazard_protection",
        "protection_from_elites",
        "skill_tier",
        "weapon_damage",
    }
)


@dataclass(frozen=True, slots=True)
class StatBlock:
    armor: float = 0.0
    armor_regen_flat: float = 0.0
    armor_regen_pct: float = 0.0
    hazard_protection: float = 0.0
    protection_from_elites: float = 0.0
    weapon_damage: float = 0.0
    skill_tier: int = 0

    def armor_regen(self) -> float:
        return self.armor_regen_flat + self.armor * self.armor_regen_pct

    def __add__(self, other: StatBlock) -> StatBlock:
        return StatBlock(
            armor=self.armor + other.armor,
            armor_regen_flat=self.armor_regen_flat + other.armor_regen_flat,
            armor_regen_pct=self.armor_regen_pct + other.armor_regen_pct,
            hazard_protection=self.hazard_protection + other.hazard_protection,
            protection_from_elites=self.protection_from_elites + other.protection_from_elites,
            weapon_damage=self.weapon_damage + other.weapon_damage,
            skill_tier=self.skill_tier + other.skill_tier,
        )


@dataclass(frozen=True, slots=True)
class ItemOption:
    item_id: str
    slot: str
    stats: StatBlock
    exotic: bool = False
    prototype: bool = False
    tags: frozenset[str] = frozenset()
    equipment_kind: EquipmentKind = EquipmentKind.GEAR
    pvp_stats: StatBlock | None = None
    conditional_stats: StatBlock = StatBlock()
    requires_tags: frozenset[str] = frozenset()
    unique_group: str | None = None

    def stats_for(self, mode: BuildMode, *, include_conditional: bool) -> StatBlock:
        base = (
            self.pvp_stats if mode == BuildMode.PVP and self.pvp_stats is not None else self.stats
        )
        return base + self.conditional_stats if include_conditional else base


@dataclass(frozen=True, slots=True)
class BuildConstraints:
    minimum_hazard_protection: float | None = None
    minimum_armor_regen: float | None = None
    minimum_armor: float | None = None
    maximum_exotics: int | None = None
    maximum_exotic_gear: int = 1
    maximum_exotic_weapons: int = 1
    maximum_prototypes: int | None = None
    required_tags: frozenset[str] = frozenset()
    required_item_ids: frozenset[str] = frozenset()
    required_slots: frozenset[str] = frozenset()
    excluded_item_ids: frozenset[str] = frozenset()
    optimize_for: tuple[str, ...] = ()
    mode: BuildMode = BuildMode.PVE
    include_conditional_buffs: bool = False
    shd_level: int = 1000
    expertise_level: int = 0

    def __post_init__(self) -> None:
        limits = (
            self.maximum_exotics,
            self.maximum_exotic_gear,
            self.maximum_exotic_weapons,
            self.maximum_prototypes,
        )
        if any(limit is not None and limit < 0 for limit in limits):
            raise ValueError("Equipment limits cannot be negative.")
        if self.shd_level < 0 or self.expertise_level < 0:
            raise ValueError("SHD and Expertise assumptions cannot be negative.")
        unknown_priorities = set(self.optimize_for) - OPTIMIZATION_PRIORITIES
        if unknown_priorities:
            raise ValueError(
                f"Unknown optimization priorities: {', '.join(sorted(unknown_priorities))}"
            )


@dataclass(slots=True)
class BuildCandidate:
    items: tuple[ItemOption, ...]
    totals: StatBlock
    legality: BuildLegality
    violations: list[str] = field(default_factory=list)
    distance: float = 0.0


@dataclass(frozen=True, slots=True)
class BuildSearchReport:
    candidates: tuple[BuildCandidate, ...]
    combinations_evaluated: int
    combinations_total: int
    exhaustive: bool
    exact_match_count: int

    @property
    def proven_impossible(self) -> bool:
        return self.exhaustive and self.exact_match_count == 0


def total_stats(
    items: Iterable[ItemOption],
    *,
    mode: BuildMode = BuildMode.PVE,
    include_conditional: bool = False,
) -> StatBlock:
    total = StatBlock()
    for item in items:
        total += item.stats_for(mode, include_conditional=include_conditional)
    return total


def validate_build(items: tuple[ItemOption, ...], constraints: BuildConstraints) -> BuildCandidate:
    violations: list[str] = []
    incomplete = False
    slots = [item.slot for item in items]
    item_ids = {item.item_id for item in items}
    if len(slots) != len(set(slots)):
        violations.append("More than one item occupies the same gear slot.")
    exotic_items = [item for item in items if item.exotic]
    if constraints.maximum_exotics is not None:
        if len(exotic_items) > constraints.maximum_exotics:
            violations.append("The build exceeds the configured total Exotic item limit.")
    else:
        exotic_gear = sum(item.equipment_kind == EquipmentKind.GEAR for item in exotic_items)
        exotic_weapons = sum(item.equipment_kind == EquipmentKind.WEAPON for item in exotic_items)
        if exotic_gear > constraints.maximum_exotic_gear:
            violations.append("The build exceeds the Exotic gear limit.")
        if exotic_weapons > constraints.maximum_exotic_weapons:
            violations.append("The build exceeds the Exotic weapon limit.")
        unsupported_exotics = sorted(
            item.item_id
            for item in exotic_items
            if item.equipment_kind not in (EquipmentKind.GEAR, EquipmentKind.WEAPON)
        )
        if unsupported_exotics:
            violations.append(
                f"Exotic limits are not configured for: {', '.join(unsupported_exotics)}."
            )
    if (
        constraints.maximum_prototypes is not None
        and sum(item.prototype for item in items) > constraints.maximum_prototypes
    ):
        violations.append("The build exceeds the configured Prototype item limit.")
    if any(item.item_id in constraints.excluded_item_ids for item in items):
        violations.append("The build contains an excluded item.")

    missing_items = constraints.required_item_ids - item_ids
    if missing_items:
        violations.append(f"Missing required items: {', '.join(sorted(missing_items))}.")

    missing_slots = constraints.required_slots - set(slots)
    if missing_slots:
        incomplete = True
        violations.append(f"Missing required slots: {', '.join(sorted(missing_slots))}.")

    present_tags = frozenset().union(*(item.tags for item in items)) if items else frozenset()
    missing_tags = constraints.required_tags - present_tags
    if missing_tags:
        violations.append(f"Missing required build tags: {', '.join(sorted(missing_tags))}.")

    for item in items:
        missing_activation_tags = item.requires_tags - present_tags
        if missing_activation_tags:
            violations.append(
                f"{item.item_id} is missing activation tags: "
                f"{', '.join(sorted(missing_activation_tags))}."
            )

    unique_groups = [item.unique_group for item in items if item.unique_group is not None]
    duplicated_groups = sorted(
        group for group in set(unique_groups) if unique_groups.count(group) > 1
    )
    if duplicated_groups:
        violations.append(f"The build duplicates unique groups: {', '.join(duplicated_groups)}.")

    totals = total_stats(
        items,
        mode=constraints.mode,
        include_conditional=constraints.include_conditional_buffs,
    )
    distance = 0.0
    thresholds = (
        ("hazard protection", totals.hazard_protection, constraints.minimum_hazard_protection),
        (
            "armor regeneration",
            totals.armor_regen(),
            constraints.minimum_armor_regen,
        ),
        ("armor", totals.armor, constraints.minimum_armor),
    )
    for label, actual, minimum in thresholds:
        if minimum is not None and actual < minimum:
            gap = minimum - actual
            distance += gap / max(abs(minimum), 1.0)
            violations.append(f"{label.title()} is short by {gap:g}.")

    return BuildCandidate(
        items=items,
        totals=totals,
        legality=(
            BuildLegality.INCOMPLETE
            if incomplete
            else BuildLegality.VALID
            if not violations
            else BuildLegality.INVALID
        ),
        violations=violations,
        distance=distance,
    )


def solve_nearest_builds(
    options_by_slot: dict[str, list[ItemOption]],
    constraints: BuildConstraints,
    *,
    limit: int = 5,
) -> list[BuildCandidate]:
    """Exhaustively find legal matches or the nearest valid-slot alternatives.

    The production optimizer will add brand/set activation, talent conditions, mods,
    Prototype rules, and encounter scoring. This bounded core deliberately performs no
    probabilistic or language-model math.
    """

    return list(
        solve_builds_with_proof(
            options_by_slot,
            constraints,
            limit=limit,
        ).candidates
    )


def solve_builds_with_proof(
    options_by_slot: dict[str, list[ItemOption]],
    constraints: BuildConstraints,
    *,
    limit: int = 5,
    maximum_combinations: int | None = None,
) -> BuildSearchReport:
    if limit < 1:
        raise ValueError("limit must be positive.")
    if maximum_combinations is not None and maximum_combinations < 1:
        raise ValueError("maximum_combinations must be positive when provided.")
    ordered_slots = sorted(options_by_slot)
    combinations_total = prod(len(options_by_slot[slot]) for slot in ordered_slots)
    combinations = product(*(options_by_slot[slot] for slot in ordered_slots))
    selected = (
        combinations if maximum_combinations is None else islice(combinations, maximum_combinations)
    )
    candidates = [validate_build(tuple(items), constraints) for items in selected]
    combinations_evaluated = len(candidates)
    exhaustive = combinations_evaluated == combinations_total
    exact_match_count = sum(candidate.legality == BuildLegality.VALID for candidate in candidates)
    candidates.sort(
        key=lambda item: (
            item.legality != BuildLegality.VALID,
            item.distance,
            *(-value for value in _optimization_values(item, constraints.optimize_for)),
        )
    )
    return BuildSearchReport(
        candidates=tuple(candidates[:limit]),
        combinations_evaluated=combinations_evaluated,
        combinations_total=combinations_total,
        exhaustive=exhaustive,
        exact_match_count=exact_match_count,
    )


def _optimization_values(
    candidate: BuildCandidate, priorities: tuple[str, ...]
) -> tuple[float, ...]:
    values = {
        "armor": candidate.totals.armor,
        "armor_regen": candidate.totals.armor_regen(),
        "hazard_protection": candidate.totals.hazard_protection,
        "protection_from_elites": candidate.totals.protection_from_elites,
        "skill_tier": float(candidate.totals.skill_tier),
        "weapon_damage": candidate.totals.weapon_damage,
    }
    return tuple(values[name] for name in priorities)
