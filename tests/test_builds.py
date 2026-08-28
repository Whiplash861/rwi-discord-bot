from __future__ import annotations

import pytest

from rwi_bot.domain.builds import (
    BuildConstraints,
    BuildLegality,
    ItemOption,
    StatBlock,
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
