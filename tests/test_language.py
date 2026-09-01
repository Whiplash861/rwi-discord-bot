from __future__ import annotations

from rwi_bot.domain.schemas import IntentKind
from rwi_bot.services.language import interpret_locally, question_signature


def test_typo_and_slang_expand_to_canonical_terms() -> None:
    interpreted = interpret_locally("Need a brocken rain build with hazzpro and regen")

    assert interpreted.intent is IntentKind.BUILD_ADVICE
    assert "broken rain" in interpreted.normalized_question
    assert "hazard protection" in interpreted.normalized_question
    assert "armor regeneration" in interpreted.normalized_question


def test_dtoc_and_dttooc_expand_to_damage_to_targets_out_of_cover() -> None:
    dtoc = interpret_locally("How much DTOC do I have?")
    dttooc = interpret_locally("Compare 8% DTTOOC with 5% DTA")

    assert "damage to targets out of cover" in dtoc.normalized_question
    assert "damage to targets out of cover" in dttooc.normalized_question


def test_common_buildcraft_aliases_expand_and_constraints_are_extracted() -> None:
    interpreted = interpret_locally(
        "Need a Heroic PvE healer build on PC with CHC, CHD, HSD, DTA, and AOK for 4 players"
    )

    assert interpreted.intent is IntentKind.BUILD_ADVICE
    assert "critical hit chance" in interpreted.normalized_question
    assert "critical hit damage" in interpreted.normalized_question
    assert "headshot damage" in interpreted.normalized_question
    assert "damage to armor" in interpreted.normalized_question
    assert "armor on kill" in interpreted.normalized_question
    assert interpreted.constraints == {
        "mode": "PvE",
        "difficulty": "Heroic",
        "role": "healer",
        "platform": "PC",
        "group_size": 4,
    }


def test_numeric_stat_goal_is_build_advice_not_item_acquisition() -> None:
    interpreted = interpret_locally("How do I get 6% armor regen?")

    assert interpreted.intent is IntentKind.BUILD_ADVICE
    assert "armor regeneration" in interpreted.normalized_question


def test_actual_drop_question_remains_acquisition() -> None:
    interpreted = interpret_locally("Where can I farm the Eagle Bearer blueprint?")
    direct = interpret_locally("How do I get Eagle Bearer?")
    drop = interpret_locally("Where does Nemesis drop?")

    assert interpreted.intent is IntentKind.ACQUISITION
    assert direct.intent is IntentKind.ACQUISITION
    assert drop.intent is IntentKind.ACQUISITION


def test_descriptive_build_review_is_build_rating() -> None:
    interpreted = interpret_locally("Review my Heroic PvE healer build on PC")

    assert interpreted.intent is IntentKind.BUILD_RATING


def test_overlapping_damage_aliases_keep_their_correct_buckets() -> None:
    interpreted = interpret_locally("Compare 20% TWD with 20% AWD and team weapon damage")

    assert "total weapon damage" in interpreted.normalized_question
    assert "all weapon damage" in interpreted.normalized_question
    assert "total all weapon damage" not in interpreted.normalized_question


def test_question_signature_is_stable_across_mapping_order() -> None:
    first = question_signature(
        "question",
        assumptions={"shd": 1000, "expertise": 0},
        constraints={"role": "tank", "mode": "pve"},
    )
    second = question_signature(
        "question",
        assumptions={"expertise": 0, "shd": 1000},
        constraints={"mode": "pve", "role": "tank"},
    )

    assert first == second
