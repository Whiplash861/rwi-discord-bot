from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process

from rwi_bot.domain.schemas import IntentKind, InterpretedQuestion

DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "hazard protection": ("hazpro", "haz pro", "hazzpro", "hazard resistance"),
    "protection from elites": ("pfe", "protection from elite", "elite protection"),
    "armor regeneration": ("armor regen", "armour regen", "regen"),
    "expertise": ("expertese", "expertice", "exptertise"),
    "prototype augment": ("proto augment", "prototype mod", "proto aug"),
    "tinkering station": ("tinker station", "tinkering bench", "workbench"),
    "Broken Rain": ("brokenrain", "brocken rain", "broken reign"),
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[^\w%+.'-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def expand_aliases(text: str) -> str:
    normalized = normalize_text(text)
    for canonical, aliases in DOMAIN_ALIASES.items():
        candidates = (normalize_text(canonical), *(normalize_text(alias) for alias in aliases))
        for alias in sorted(candidates, key=len, reverse=True):
            normalized = re.sub(rf"\b{re.escape(alias)}\b", normalize_text(canonical), normalized)
    return normalized


def question_signature(
    normalized_question: str,
    *,
    assumptions: dict[str, Any],
    constraints: dict[str, Any] | None = None,
) -> str:
    payload = {
        "q": normalized_question,
        "assumptions": assumptions,
        "constraints": constraints or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class FuzzyCandidate:
    value: str
    score: float


def fuzzy_candidates(query: str, vocabulary: list[str], *, limit: int = 3) -> list[FuzzyCandidate]:
    if not query or not vocabulary:
        return []
    matches = process.extract(
        normalize_text(query),
        vocabulary,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=55,
    )
    return [FuzzyCandidate(value=value, score=float(score) / 100.0) for value, score, _ in matches]


def interpret_locally(question: str) -> InterpretedQuestion:
    normalized = expand_aliases(question)
    intent = IntentKind.FACT
    if any(token in normalized for token in ("build", "loadout", "setup")):
        intent = IntentKind.BUILD_ADVICE
    if any(token in normalized for token in ("rate my", "rating", "grade my")):
        intent = IntentKind.BUILD_RATING
    elif any(token in normalized for token in ("where do i get", "how do i get", "drop", "farm")):
        intent = IntentKind.ACQUISITION
    elif any(token in normalized for token in ("what changed", "patch", "title update")):
        intent = IntentKind.PATCH_HISTORY
    elif any(token in normalized for token in ("mission", "strategy", "guide")):
        intent = IntentKind.MISSION_GUIDE

    entities = [
        canonical for canonical in DOMAIN_ALIASES if normalize_text(canonical) in normalized
    ]
    return InterpretedQuestion(
        intent=intent,
        normalized_question=normalized,
        entities=entities,
        confidence=0.82 if entities else 0.66,
    )
