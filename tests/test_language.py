from __future__ import annotations

from rwi_bot.domain.schemas import IntentKind
from rwi_bot.services.language import interpret_locally, question_signature


def test_typo_and_slang_expand_to_canonical_terms() -> None:
    interpreted = interpret_locally("Need a brocken rain build with hazzpro and regen")

    assert interpreted.intent is IntentKind.BUILD_ADVICE
    assert "broken rain" in interpreted.normalized_question
    assert "hazard protection" in interpreted.normalized_question
    assert "armor regeneration" in interpreted.normalized_question


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
