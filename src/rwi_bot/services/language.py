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
    "damage to targets out of cover": (
        "dtoc",
        "dttooc",
        "damage to target out of cover",
        "out of cover damage",
    ),
    "critical hit chance": ("chc", "crit chance", "critical chance"),
    "critical hit damage": ("chd", "crit damage", "critical damage"),
    "headshot damage": ("hsd", "headshot dmg", "head shot damage"),
    "damage to armor": ("dta", "armour damage", "damage against armor"),
    "damage to health": ("dth", "health damage", "damage against health"),
    "armor on kill": ("aok", "armour on kill"),
    "all weapon damage": ("awd", "weapon dmg", "weapon damage"),
    "total weapon damage": ("twd", "total weapon dmg"),
    "skill damage": ("skill dmg",),
    "skill haste": ("skill cooldown", "cooldown reduction"),
    "repair skills": ("repair skill", "skill repair", "healing skills"),
    "status effects": ("status effect", "status build"),
    "critical hit cap": ("crit cap", "chc cap"),
    "tinkering station": ("tinker station", "tinkering bench", "workbench"),
    "Broken Rain": ("brokenrain", "brocken rain", "broken reign"),
    "Paradise Lost": ("meret estate", "merit estate", "paradise lost incursion"),
    "Operation Dark Hours": ("dark hours", "odh", "airport raid"),
    "Operation Iron Horse": ("iron horse", "ih raid", "foundry raid"),
    "Dark Zone": ("dz", "darkzone"),
}

_BUILD_TERMS = (
    "build",
    "loadout",
    "setup",
    "gear for",
    "best gear",
    "reach ",
    "stack ",
)
_ACQUISITION_PATTERNS = (
    r"\bwhere (?:do|can|should) i (?:get|find|farm|obtain)\b",
    r"\bhow (?:do|can) i (?:get|find|farm|obtain|unlock)\b",
    r"\b(?:drop|loot|farm|acquisition|blueprint|crafting) (?:source|location|route)\b",
    r"\bwhat drops\b",
    r"\b(?:drop|drops|dropped|farmable|obtainable)\b",
)
_STAT_VALUE_REQUEST = re.compile(
    r"\b(?:get|reach|make|build|stack)\b.{0,28}(?:\d+(?:\.\d+)?\s*%|"
    r"critical hit|headshot|armor|health|hazard|skill tier|resistance|damage)",
)
_DIFFICULTIES = ("story", "normal", "hard", "challenging", "heroic", "legendary", "master")
_ROLES = ("tank", "healer", "medic", "support", "dps", "sniper", "drone killer", "kite")
_PLATFORMS = ("pc", "xbox", "playstation", "ps4", "ps5")


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[^\w%+.'-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def expand_aliases(text: str) -> str:
    normalized = normalize_text(text)
    replacements: dict[str, str] = {}
    for canonical, aliases in DOMAIN_ALIASES.items():
        target = normalize_text(canonical)
        replacements[target] = target
        replacements.update({normalize_text(alias): target for alias in aliases})
    pattern = "|".join(re.escape(value) for value in sorted(replacements, key=len, reverse=True))
    return re.sub(
        rf"(?<!\w)(?:{pattern})(?!\w)",
        lambda match: replacements[normalize_text(match.group(0))],
        normalized,
    )


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
    if any(token in normalized for token in _BUILD_TERMS) or _STAT_VALUE_REQUEST.search(normalized):
        intent = IntentKind.BUILD_ADVICE
    if re.search(
        r"\b(?:rate|grade|review|evaluate)\b.{0,80}\b(?:my|this|the)\b.{0,40}"
        r"\b(?:build|loadout|setup)\b",
        normalized,
    ) or any(token in normalized for token in ("rating", "build rating")):
        intent = IntentKind.BUILD_RATING
    elif intent is not IntentKind.BUILD_ADVICE and any(
        re.search(pattern, normalized) for pattern in _ACQUISITION_PATTERNS
    ):
        intent = IntentKind.ACQUISITION
    elif any(
        token in normalized for token in ("what changed", "patch", "title update", "known issue")
    ):
        intent = IntentKind.PATCH_HISTORY
    elif any(
        token in normalized
        for token in (
            "mission",
            "strategy",
            "guide",
            "walkthrough",
            "how do i beat",
            "how do i beet",
            "how do we beat",
            "mechanics",
            "boss fight",
        )
    ):
        intent = IntentKind.MISSION_GUIDE
    elif any(
        token in normalized
        for token in ("what do you know about me", "what do you remember about me", "my profile")
    ):
        intent = IntentKind.PROFILE

    entities = [
        canonical for canonical in DOMAIN_ALIASES if normalize_text(canonical) in normalized
    ]
    constraints = _extract_constraints(normalized)
    return InterpretedQuestion(
        intent=intent,
        normalized_question=normalized,
        entities=entities,
        constraints=constraints,
        confidence=0.9 if entities and constraints else 0.84 if entities else 0.72,
    )


def _extract_constraints(normalized: str) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    if re.search(r"\bpve\b|player versus environment", normalized):
        constraints["mode"] = "PvE"
    if re.search(r"\bpvp\b|player versus player", normalized):
        constraints["mode"] = "PvE and PvP" if constraints.get("mode") == "PvE" else "PvP"
    if "dark zone" in normalized:
        constraints["activity_mode"] = "Dark Zone"

    difficulties = [value.title() for value in _DIFFICULTIES if _word(normalized, value)]
    if difficulties:
        constraints["difficulty"] = difficulties[0] if len(difficulties) == 1 else difficulties

    roles = [value for value in _ROLES if _word(normalized, value)]
    if roles:
        constraints["role"] = roles[0] if len(roles) == 1 else roles

    platforms = [
        value.upper() if value == "pc" else value.title()
        for value in _PLATFORMS
        if _word(normalized, value)
    ]
    if platforms:
        constraints["platform"] = platforms[0] if len(platforms) == 1 else platforms

    players = re.search(r"\b(?:for|with)\s+([1-8])\s*(?:players?|agents?|people)\b", normalized)
    if players:
        constraints["group_size"] = int(players.group(1))
    return constraints


def _word(text: str, value: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text) is not None
