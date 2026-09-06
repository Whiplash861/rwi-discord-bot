from __future__ import annotations

from rwi_bot.services.build_intent import build_scope_prompt, identify_build_request
from rwi_bot.services.encounter_intent import predict_encounter_request
from rwi_bot.services.language import interpret_locally


def test_broad_best_dps_request_requires_current_meta_comparison() -> None:
    interpreted = interpret_locally("What is the best DPS build?")

    scope = identify_build_request(
        interpreted=interpreted,
        encounter=None,
        reference_hits=[],
        current_game_version="Y8S3 Red Horizon",
    )

    assert scope is not None
    assert scope.kind == "broad"
    assert scope.objective == "weapon DPS"
    assert scope.subjective_superlative is True
    assert scope.requires_live_meta_search is True
    assert any("community meta" in query for query in scope.retrieval_queries)
    prompt = build_scope_prompt(scope)
    assert "do not stop at saying that 'best' is subjective" in prompt
    assert "high-yield experiment" in prompt


def test_broken_rain_build_request_maps_to_activity_roles_and_swaps() -> None:
    question = "What build should I use for Broken Rain?"
    interpreted = interpret_locally(question)
    encounter = predict_encounter_request(question)

    scope = identify_build_request(
        interpreted=interpreted,
        encounter=encounter,
        reference_hits=[],
        current_game_version="Y8S3 Red Horizon",
    )

    assert scope is not None
    assert scope.kind == "activity"
    assert scope.activity == "Broken Rain"
    assert scope.requires_live_meta_search is False
    assert any("role build matrix" in query for query in scope.retrieval_queries)
    assert any("encounter swap points" in value for value in scope.response_directives)


def test_generic_legendary_build_request_is_activity_scoped() -> None:
    interpreted = interpret_locally("What DPS build should I use for Legendary missions?")

    scope = identify_build_request(
        interpreted=interpreted,
        encounter=None,
        reference_hits=[],
        current_game_version="Y8S3 Red Horizon",
    )

    assert scope is not None
    assert scope.kind == "activity"
    assert scope.activity == "Legendary missions"
    assert scope.objective == "weapon DPS"
