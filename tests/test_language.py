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
