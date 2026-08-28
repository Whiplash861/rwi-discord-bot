from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import product


class BuildLegality(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    INCOMPLETE = "incomplete"


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


@dataclass(frozen=True, slots=True)
class BuildConstraints:
    minimum_hazard_protection: float | None = None
    minimum_armor_regen: float | None = None
    minimum_armor: float | None = None
    maximum_exotics: int = 1
    required_tags: frozenset[str] = frozenset()
    excluded_item_ids: frozenset[str] = frozenset()
    optimize_for: tuple[str, ...] = ()


@dataclass(slots=True)
class BuildCandidate:
    items: tuple[ItemOption, ...]
    totals: StatBlock
    legality: BuildLegality
    violations: list[str] = field(default_factory=list)
    distance: float = 0.0


def total_stats(items: Iterable[ItemOption]) -> StatBlock:
    total = StatBlock()
    for item in items:
        total += item.stats
    return total


def validate_build(items: tuple[ItemOption, ...], constraints: BuildConstraints) -> BuildCandidate:
    violations: list[str] = []
    slots = [item.slot for item in items]
    if len(slots) != len(set(slots)):
        violations.append("More than one item occupies the same gear slot.")
    if sum(item.exotic for item in items) > constraints.maximum_exotics:
        violations.append("The build exceeds the configured Exotic item limit.")
    if any(item.item_id in constraints.excluded_item_ids for item in items):
        violations.append("The build contains an excluded item.")

    present_tags = frozenset().union(*(item.tags for item in items)) if items else frozenset()
    missing_tags = constraints.required_tags - present_tags
    if missing_tags:
        violations.append(f"Missing required build tags: {', '.join(sorted(missing_tags))}.")

    totals = total_stats(items)
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
        legality=BuildLegality.VALID if not violations else BuildLegality.INVALID,
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

    ordered_slots = sorted(options_by_slot)
    combinations = product(*(options_by_slot[slot] for slot in ordered_slots))
    candidates = [validate_build(tuple(items), constraints) for items in combinations]
    candidates.sort(
        key=lambda item: (
            item.legality != BuildLegality.VALID,
            item.distance,
            *(-value for value in _optimization_values(item, constraints.optimize_for)),
        )
    )
    return candidates[:limit]


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
    unknown = [name for name in priorities if name not in values]
    if unknown:
        raise ValueError(f"Unknown optimization priorities: {', '.join(unknown)}")
    return tuple(values[name] for name in priorities)
