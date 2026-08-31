from __future__ import annotations

from decimal import Decimal

import pytest

from rwi_bot.services.damage_math import (
    Amplifier,
    DamageInputs,
    calculate_weapon_hit,
    parse_damage_question,
    render_damage_breakdown,
)


def test_damage_sequence_applies_each_bucket_and_shows_work() -> None:
    result = calculate_weapon_hit(
        DamageInputs(
            base_damage=Decimal("100000"),
            weapon_damage=Decimal("1.0"),
            weapon_type_damage=Decimal("0.2"),
            total_weapon_damage=Decimal("0.25"),
            headshot_damage=Decimal("1.0"),
            critical_hit_damage=Decimal("1.5"),
            damage_to_armor=Decimal("0.06"),
            damage_to_targets_out_of_cover=Decimal("0.10"),
            amplifiers=(Amplifier("team debuff", Decimal("0.15"), team_buff=True),),
            headshot=True,
            critical_hit=True,
            target_has_armor=True,
            target_has_health=False,
            target_out_of_cover=True,
        )
    )

    assert result.final_damage == Decimal("1290616.2500000000")
    assert [step.name for step in result.steps] == [
        "Base weapon damage",
        "Weapon Damage bucket",
        "Total Weapon Damage bucket",
        "Hit-location and critical bucket",
        "Target-layer damage",
        "Damage to Targets Out of Cover (DTOC/DTTOOC)",
        "Amplified damage — team debuff",
    ]
    rendered = render_damage_breakdown(result)
    assert "Running damage" in rendered
    assert "Final damage per projectile" in rendered
    assert "1,290,616.2500" in rendered


def test_expected_crit_uses_chance_times_critical_damage() -> None:
    result = calculate_weapon_hit(
        DamageInputs(
            base_damage=Decimal("100"),
            critical_hit_chance=Decimal("0.50"),
            critical_hit_damage=Decimal("1.00"),
            expected_critical_value=True,
        )
    )

    assert result.final_damage == Decimal("150.0000")
    assert "CHC \N{MULTIPLICATION SIGN} CHD" in result.steps[3].formula


def test_target_armor_and_health_bonuses_are_layer_conditional() -> None:
    armored = calculate_weapon_hit(
        DamageInputs(
            base_damage=Decimal("100"),
            damage_to_armor=Decimal("0.10"),
            damage_to_health=Decimal("0.25"),
            target_has_armor=True,
            target_has_health=False,
        )
    )
    health = calculate_weapon_hit(
        DamageInputs(
            base_damage=Decimal("100"),
            damage_to_armor=Decimal("0.10"),
            damage_to_health=Decimal("0.25"),
            target_has_armor=False,
            target_has_health=True,
        )
    )

    assert armored.final_damage == Decimal("110.000")
    assert health.final_damage == Decimal("125.000")


def test_critical_chance_cannot_exceed_division_two_cap() -> None:
    with pytest.raises(ValueError, match="60% cap"):
        calculate_weapon_hit(
            DamageInputs(
                base_damage=Decimal("100"),
                critical_hit_chance=Decimal("0.61"),
                expected_critical_value=True,
            )
        )


def test_labeled_natural_language_damage_question_is_parsed_deterministically() -> None:
    parsed = parse_damage_question(
        "Show me the damage math: base damage 100,000, weapon damage 120%, total weapon "
        "damage 25%, HSD 100%, CHD 150%, DTA 6%, DTOC 10%, team amplified damage 15%. "
        "The shot is a headshot and a critical hit against an armored target out of cover."
    )

    assert parsed is not None
    assert parsed.base_damage == Decimal("100000")
    assert parsed.weapon_damage == Decimal("1.20")
    assert parsed.total_weapon_damage == Decimal("0.25")
    assert parsed.headshot
    assert parsed.critical_hit
    assert parsed.target_has_armor
    assert parsed.target_out_of_cover
    assert parsed.amplifiers == (Amplifier("Amplifier 1", Decimal("0.15"), team_buff=True),)


def test_damage_parser_requires_explicit_intent_and_base_damage() -> None:
    assert parse_damage_question("My build has 150% CHD") is None
    assert parse_damage_question("Calculate my build with 150% CHD") is None
