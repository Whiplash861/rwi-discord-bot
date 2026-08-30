from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class FeedbackSentiment(StrEnum):
    HELPFUL = "helpful"
    INCORRECT = "incorrect"


@dataclass(frozen=True, slots=True)
class InferredFeedback:
    sentiment: FeedbackSentiment
    feedback_only: bool
    matched_cue: str


_NEGATIVE_CUES = (
    re.compile(
        r"\b(?:that|this|it)\s+(?:did not|didn't|does not|doesn't)\s+(?:help|work)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:that|this|it|your answer)(?:\s+(?:is|was)|'s)\s+"
        r"(?:wrong|incorrect|outdated)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\byou(?:'re| are)\s+wrong\b", re.IGNORECASE),
    re.compile(r"\b(?:incorrect|outdated)\s+(?:answer|information|info)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:that|this|it|your answer)(?:\s+(?:is|was)|'s)\s+not\s+helpful\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bnot\s+(?:helpful|what i asked(?: for)?)\b", re.IGNORECASE),
    re.compile(r"\b(?:did not|didn't|does not|doesn't)\s+(?:help|work)\b", re.IGNORECASE),
    re.compile(r"\b(?:you|erin)\s+made\s+that\s+up\b", re.IGNORECASE),
    re.compile(r"\b(?:bad|false)\s+(?:information|info)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:wrong|incorrect|outdated)\s*[.!]*\s*$", re.IGNORECASE),
)

_POSITIVE_CUES = (
    re.compile(r"\bthanks\s+for\s+(?:your|the)\s+help\b", re.IGNORECASE),
    re.compile(r"\bthank\s+you\b", re.IGNORECASE),
    re.compile(r"\bthanks\b", re.IGNORECASE),
    re.compile(r"\b(?:that|this|it)\s+(?:was\s+helpful|worked|helped)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:very\s+)?helpful\s*[.!]*\s*$", re.IGNORECASE),
    re.compile(r"\bexactly\s+what\s+i\s+needed\b", re.IGNORECASE),
    re.compile(r"\b(?:great|good)\s+answer\b", re.IGNORECASE),
    re.compile(r"\byou\s+nailed\s+it\b", re.IGNORECASE),
    re.compile(r"\bgot\s+it\b", re.IGNORECASE),
    re.compile(r"^\s*perfect\s*[.!]*\s*$", re.IGNORECASE),
)

_AMBIGUOUS_NEGATIVE_QUESTION = re.compile(
    r"^\s*(?:is|was|could|might|would)\s+(?:that|this|it|your answer)\s+"
    r"(?:be\s+)?(?:wrong|incorrect|outdated)\s*\?\s*$",
    re.IGNORECASE,
)

_FEEDBACK_FILLER = re.compile(
    r"\b(?:erin|okay|ok|alright|cool|awesome|again|really|very|so|much|perfectly|"
    r"for that|though|yep|yeah|please)\b",
    re.IGNORECASE,
)


def infer_feedback(text: str) -> InferredFeedback | None:
    """Infer only explicit, high-confidence feedback about the immediately prior answer."""

    clean = " ".join(text.strip().split())
    if not clean or _AMBIGUOUS_NEGATIVE_QUESTION.fullmatch(clean):
        return None

    negative = _first_match(clean, _NEGATIVE_CUES)
    positive = _first_match(clean, _POSITIVE_CUES)
    match = negative or positive
    if match is None:
        return None

    sentiment = FeedbackSentiment.INCORRECT if negative is not None else FeedbackSentiment.HELPFUL
    return InferredFeedback(
        sentiment=sentiment,
        feedback_only=_is_feedback_only(clean),
        matched_cue=match.group(0).casefold(),
    )


def _first_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> re.Match[str] | None:
    for pattern in patterns:
        if match := pattern.search(text):
            return match
    return None


def _is_feedback_only(text: str) -> bool:
    remainder = text
    for pattern in (*_NEGATIVE_CUES, *_POSITIVE_CUES):
        remainder = pattern.sub(" ", remainder)
    remainder = _FEEDBACK_FILLER.sub(" ", remainder)
    remainder = re.sub(r"[^a-z0-9]+", " ", remainder.casefold()).strip()
    return not remainder
