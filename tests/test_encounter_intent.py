from __future__ import annotations

import pytest

from rwi_bot.services.encounter_intent import predict_encounter_request


@pytest.mark.parametrize(
    ("question", "activity", "encounter"),
    [
        (
            "How do I beat the Lovebirds in the meret estate incursion?",
            "Paradise Lost",
            "The Lovebirds: Martinez and Johnson",
        ),
        (
            "How do I beat the lovebirds?",
            "Paradise Lost",
            "The Lovebirds: Martinez and Johnson",
        ),
        ("How do I beat Wright in the merit estate?", "Paradise Lost", "Wright"),
        ("How do I beat Iris Steel?", "Broken Rain", "Iris Steel"),
        ("Need a build for Lester", "Broken Rain", "Lester Steel"),
        ("Explain Razorback mechanics", "Operation Dark Hours", "DDP-52 Razorback"),
        (
            "Give me the Morozova strategy",
            "Operation Iron Horse",
            "Colonel Morozova and the Iron Horse",
        ),
    ],
)
def test_predictive_resolver_maps_boss_phrasings_to_canonical_encounters(
    question: str, activity: str, encounter: str
) -> None:
    prediction = predict_encounter_request(question)

    assert prediction is not None
    assert prediction.clarification is None
    assert prediction.activity == activity
    assert prediction.encounter == encounter
    assert activity in prediction.search_query
    assert encounter in prediction.search_query


def test_predictive_resolver_expands_a_full_activity_guide() -> None:
    prediction = predict_encounter_request(
        "Give me a complete walkthrough for every encounter in Broken Reign"
    )

    assert prediction is not None
    assert prediction.activity == "Broken Rain"
    assert prediction.encounter is None
    assert prediction.request_kind == "activity_guide"
    assert "recommended builds" in prediction.search_query


def test_predictive_resolver_recovers_a_confident_typo() -> None:
    prediction = predict_encounter_request("How do we beat the Lovrbirds boss?")

    assert prediction is not None
    assert prediction.encounter == "The Lovebirds: Martinez and Johnson"
    assert prediction.clarification is None


def test_predictive_resolver_asks_when_multiple_encounters_share_the_wording() -> None:
    prediction = predict_encounter_request("How do I beat Steel?")

    assert prediction is not None
    assert prediction.encounter is None
    assert prediction.clarification is not None
    assert "Lester Steel" in prediction.clarification
    assert "Iris Steel" in prediction.clarification


def test_predictive_resolver_does_not_hijack_unrelated_questions() -> None:
    assert predict_encounter_request("What is critical hit chance?") is None
