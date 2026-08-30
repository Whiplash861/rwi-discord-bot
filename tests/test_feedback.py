from __future__ import annotations

import pytest

from rwi_bot.services.feedback import FeedbackSentiment, infer_feedback


@pytest.mark.parametrize(
    "text",
    (
        "Thanks!",
        "Thank you, ERIN.",
        "That worked perfectly.",
        "This was helpful.",
        "Exactly what I needed.",
        "Great answer.",
    ),
)
def test_explicit_helpful_feedback_is_inferred(text: str) -> None:
    result = infer_feedback(text)

    assert result is not None
    assert result.sentiment is FeedbackSentiment.HELPFUL
    assert result.feedback_only is True


@pytest.mark.parametrize(
    "text",
    (
        "That's wrong.",
        "This is outdated.",
        "That didn't work.",
        "You made that up.",
        "Incorrect.",
        "That was not helpful.",
    ),
)
def test_explicit_incorrect_feedback_is_inferred(text: str) -> None:
    result = infer_feedback(text)

    assert result is not None
    assert result.sentiment is FeedbackSentiment.INCORRECT
    assert result.feedback_only is True


def test_negative_feedback_takes_precedence_over_thanks() -> None:
    result = infer_feedback("Thanks, but that's outdated.")

    assert result is not None
    assert result.sentiment is FeedbackSentiment.INCORRECT


@pytest.mark.parametrize("text", ("Is that outdated?", "Could this be wrong?"))
def test_uncertain_question_is_not_misread_as_feedback(text: str) -> None:
    assert infer_feedback(text) is None


def test_feedback_with_a_new_question_continues_as_a_normal_request() -> None:
    result = infer_feedback("Thanks. How do I recalibrate it?")

    assert result is not None
    assert result.sentiment is FeedbackSentiment.HELPFUL
    assert result.feedback_only is False


@pytest.mark.parametrize("text", ("Perfect Striker build?", "Helpful gear list?"))
def test_answer_words_inside_new_questions_are_not_feedback(text: str) -> None:
    assert infer_feedback(text) is None
