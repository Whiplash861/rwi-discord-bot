from __future__ import annotations

from rwi_bot.services.skill_scope import (
    identify_broad_skill_family,
    render_variant_clarification,
    response_covers_every_variant,
    skill_scope_prompt,
)


def test_broad_shield_question_resolves_to_every_current_variant() -> None:
    request = identify_broad_skill_family("What is the Shield's overcharge bonus?")

    assert request is not None
    assert request.family.name == "Ballistic Shield"
    assert request.variant_names == (
        "Bulwark Shield",
        "Crusader Shield",
        "Deflector Shield",
        "Striker Shield",
    )
    assert "never silently answer for just one variant" in skill_scope_prompt(request)


def test_named_skill_variant_is_not_misclassified_as_a_family() -> None:
    assert identify_broad_skill_family("What is the Assault Turret overcharge bonus?") is None
    assert identify_broad_skill_family("How much health does the Crusader Shield have?") is None
    assert identify_broad_skill_family("What does the Decoy do?") is None


def test_family_answer_must_name_every_variant() -> None:
    request = identify_broad_skill_family("Compare all Shield variants")

    assert request is not None
    assert request.explicitly_requests_all is True
    assert response_covers_every_variant("Bulwark Shield is invulnerable.", request) is False
    assert (
        response_covers_every_variant(
            "Bulwark Shield, Crusader Shield, Deflector Shield, and Striker Shield all gain "
            "Shield Wall.",
            request,
        )
        is True
    )


def test_family_clarification_is_focused_and_complete() -> None:
    request = identify_broad_skill_family("What does a Shield do?")

    assert request is not None
    clarification = render_variant_clarification(request)
    assert "Which one do you mean" in clarification
    assert all(name in clarification for name in request.variant_names)
    assert "all Shield variants" in clarification
