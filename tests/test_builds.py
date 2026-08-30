from __future__ import annotations

import pytest

from rwi_bot.domain.builds import (
    BuildConstraints,
    BuildLegality,
    BuildMode,
    EquipmentKind,
    ItemOption,
    StatBlock,
    solve_builds_with_proof,
    solve_nearest_builds,
    validate_build,
)


def test_duplicate_slot_and_exotic_limit_are_illegal() -> None:
    items = (
        ItemOption("exotic-a", "mask", StatBlock(), exotic=True),
        ItemOption("exotic-b", "mask", StatBlock(), exotic=True),
    )

    result = validate_build(items, BuildConstraints(maximum_exotics=1))

    assert result.legality is BuildLegality.INVALID
    assert len(result.violations) == 2


def test_broken_rain_tank_prioritizes_hazard_protection_then_regen() -> None:
    options = {
        "chest": [
            ItemOption(
                "hazard-chest",
                "chest",
                StatBlock(armor=900_000, armor_regen_pct=0.01, hazard_protection=0.50),
                tags=frozenset({"broken-rain", "tank"}),
            )
        ],
        "mask": [
            ItemOption(
                "low-regen-mask",
                "mask",
                StatBlock(armor=100_000, armor_regen_flat=1_000, hazard_protection=0.50),
            ),
            ItemOption(
                "high-regen-mask",
                "mask",
                StatBlock(armor=100_000, armor_regen_flat=4_000, hazard_protection=0.50),
            ),
        ],
    }
    constraints = BuildConstraints(
        minimum_hazard_protection=1.0,
        required_tags=frozenset({"broken-rain", "tank"}),
        optimize_for=("hazard_protection", "armor_regen"),
    )

    results = solve_nearest_builds(options, constraints, limit=2)

    assert len(results) == 2
    assert all(result.legality is BuildLegality.VALID for result in results)
    assert results[0].totals.hazard_protection == pytest.approx(1.0)
    assert results[0].items[1].item_id == "high-regen-mask"
    assert results[0].totals.armor_regen() == pytest.approx(14_000)


def test_solver_returns_nearest_exhaustive_alternative_when_exact_is_impossible() -> None:
    options = {
        "chest": [ItemOption("chest", "chest", StatBlock(hazard_protection=0.45))],
        "mask": [
            ItemOption("mask-a", "mask", StatBlock(hazard_protection=0.40)),
            ItemOption("mask-b", "mask", StatBlock(hazard_protection=0.50)),
        ],
    }

    results = solve_nearest_builds(
        options,
        BuildConstraints(minimum_hazard_protection=1.0),
        limit=2,
    )

    assert len(results) == 2
    assert results[0].totals.hazard_protection == pytest.approx(0.95)
    assert results[0].distance < results[1].distance


def test_unknown_optimization_priority_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown optimization"):
        solve_nearest_builds(
            {"mask": [ItemOption("mask", "mask", StatBlock())]},
            BuildConstraints(optimize_for=("imaginary_stat",)),
        )


def test_exotic_limits_are_enforced_per_equipment_category() -> None:
    legal = (
        ItemOption("exotic-mask", "mask", StatBlock(), exotic=True),
        ItemOption(
            "exotic-rifle",
            "primary",
            StatBlock(),
            exotic=True,
            equipment_kind=EquipmentKind.WEAPON,
        ),
    )

    assert validate_build(legal, BuildConstraints()).legality == BuildLegality.VALID

    two_exotic_gear = (
        legal[0],
        ItemOption("exotic-chest", "chest", StatBlock(), exotic=True),
    )
    result = validate_build(two_exotic_gear, BuildConstraints())
    assert result.legality == BuildLegality.INVALID
    assert "Exotic gear limit" in result.violations[0]

    unsupported = validate_build(
        (
            ItemOption(
                "exotic-skill",
                "skill-one",
                StatBlock(),
                exotic=True,
                equipment_kind=EquipmentKind.SKILL,
            ),
        ),
        BuildConstraints(),
    )
    assert unsupported.legality == BuildLegality.INVALID
    assert "not configured" in unsupported.violations[0]


def test_mode_variants_and_conditional_buffs_are_explicit() -> None:
    item = ItemOption(
        "mode-sensitive",
        "chest",
        StatBlock(weapon_damage=0.20),
        pvp_stats=StatBlock(weapon_damage=0.10),
        conditional_stats=StatBlock(weapon_damage=0.25),
    )

    permanent = validate_build(
        (item,),
        BuildConstraints(mode=BuildMode.PVP, include_conditional_buffs=False),
    )
    conditional = validate_build(
        (item,),
        BuildConstraints(mode=BuildMode.PVP, include_conditional_buffs=True),
    )

    assert permanent.totals.weapon_damage == pytest.approx(0.10)
    assert conditional.totals.weapon_damage == pytest.approx(0.35)


def test_activation_unique_group_and_completeness_rules_are_deterministic() -> None:
    items = (
        ItemOption(
            "activated-mask",
            "mask",
            StatBlock(),
            requires_tags=frozenset({"four-piece-set"}),
            unique_group="named-family",
        ),
        ItemOption(
            "named-chest",
            "chest",
            StatBlock(),
            unique_group="named-family",
        ),
    )

    result = validate_build(
        items,
        BuildConstraints(required_slots=frozenset({"mask", "chest", "backpack"})),
    )

    assert result.legality == BuildLegality.INCOMPLETE
    assert any("activation tags" in violation for violation in result.violations)
    assert any("unique groups" in violation for violation in result.violations)
    assert any("Missing required slots" in violation for violation in result.violations)


def test_impossibility_is_claimed_only_after_exhaustive_search() -> None:
    options = {
        "mask": [
            ItemOption("mask-a", "mask", StatBlock(armor=100)),
            ItemOption("mask-b", "mask", StatBlock(armor=200)),
        ],
        "chest": [
            ItemOption("chest-a", "chest", StatBlock(armor=100)),
            ItemOption("chest-b", "chest", StatBlock(armor=200)),
        ],
    }
    impossible = BuildConstraints(minimum_armor=1000)

    partial = solve_builds_with_proof(
        options,
        impossible,
        maximum_combinations=2,
    )
    exhaustive = solve_builds_with_proof(options, impossible)

    assert partial.combinations_evaluated == 2
    assert partial.combinations_total == 4
    assert partial.exhaustive is False
    assert partial.proven_impossible is False
    assert exhaustive.combinations_evaluated == 4
    assert exhaustive.exhaustive is True
    assert exhaustive.proven_impossible is True
