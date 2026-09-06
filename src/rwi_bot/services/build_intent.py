from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from rwi_bot.domain.schemas import IntentKind, InterpretedQuestion
from rwi_bot.services.encounter_intent import EncounterPrediction
from rwi_bot.services.language import normalize_text
from rwi_bot.services.reference_catalog import ReferenceHit, is_specific_reference_hit

BuildRequestKind = Literal["broad", "activity", "specific"]


@dataclass(frozen=True, slots=True)
class BuildRequestScope:
    """Deterministic build-planning context; this class never supplies game facts."""

    kind: BuildRequestKind
    objective: str
    activity: str | None
    encounter: str | None
    subjective_superlative: bool
    asks_for_popularity: bool
    requires_live_meta_search: bool
    retrieval_queries: tuple[str, ...]
    response_directives: tuple[str, ...]


_SUPERLATIVE_PATTERNS = (
    r"\bbest\b",
    r"\bstrongest\b",
    r"\btop\s+(?:tier|build|dps)\b",
    r"\bhighest\s+(?:damage|dps|output)\b",
    r"\boptimal\b",
    r"\bmeta\b",
)
_POPULARITY_PATTERNS = (
    r"\bpopular\b",
    r"\bcommunity\s+(?:build|choice|meta|setup)\b",
    r"\bmost\s+(?:used|common)\b",
    r"\bwhat (?:are|is) people (?:running|using)\b",
)
_OBJECTIVES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("weapon DPS", ("weapon dps", "gun dps", "dps", "damage dealer", "red build")),
    ("skill DPS", ("skill dps", "skill damage", "turret drone", "drone turret")),
    ("healer", ("healer", "medic", "healing", "repair build")),
    ("tank", ("tank", "tanking", "protection from elites", "pfe")),
    ("support", ("support", "team buff", "crowd control", "cc build")),
    ("status effects", ("status effects", "status build", "burn build", "bleed build")),
    ("sniper", ("sniper", "marksman", "mmr build")),
)
_ACTIVITY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Legendary missions", ("legendary mission", "legendary stronghold", "legendary")),
    ("Escalation", ("escalation", "tier 10", "t10")),
    ("Countdown", ("countdown",)),
    ("Descent", ("descent",)),
    ("The Summit", ("the summit", "summit")),
    ("Dark Zone", ("dark zone", "toxic dz", "blackout dz", "invaded dz")),
    ("Raid", ("raid",)),
    ("Incursion", ("incursion",)),
)


def identify_build_request(
    *,
    interpreted: InterpretedQuestion,
    encounter: EncounterPrediction | None,
    reference_hits: Iterable[ReferenceHit],
    current_game_version: str,
) -> BuildRequestScope | None:
    if interpreted.intent not in {IntentKind.BUILD_ADVICE, IntentKind.BUILD_RATING}:
        return None

    normalized = interpreted.normalized_question
    subjective = any(re.search(pattern, normalized) for pattern in _SUPERLATIVE_PATTERNS)
    asks_for_popularity = any(re.search(pattern, normalized) for pattern in _POPULARITY_PATTERNS)
    objective = _objective(normalized, interpreted)
    activity = encounter.activity if encounter is not None else _activity(normalized, interpreted)
    encounter_name = encounter.encounter if encounter is not None else None
    specific_reference = any(
        is_specific_reference_hit(hit)
        and (
            (hit.match_kind == "exact" and hit.score >= 0.60)
            or (hit.match_kind == "fuzzy" and hit.score >= 0.75)
        )
        for hit in reference_hits
    )

    if activity is not None:
        kind: BuildRequestKind = "activity"
    elif subjective or asks_for_popularity or not specific_reference:
        kind = "broad"
    else:
        kind = "specific"

    # Broad recommendations and explicit meta/popularity questions are time-sensitive.
    # The live search provides community-use signals; all factual mechanics remain gated
    # by the normal evidence rules.
    requires_live_search = kind == "broad" or subjective or asks_for_popularity
    queries = _retrieval_queries(
        normalized=normalized,
        current_game_version=current_game_version,
        objective=objective,
        activity=activity,
        encounter=encounter_name,
        kind=kind,
    )
    directives = _response_directives(
        kind=kind,
        objective=objective,
        activity=activity,
        subjective=subjective,
    )
    return BuildRequestScope(
        kind=kind,
        objective=objective,
        activity=activity,
        encounter=encounter_name,
        subjective_superlative=subjective,
        asks_for_popularity=asks_for_popularity,
        requires_live_meta_search=requires_live_search,
        retrieval_queries=queries,
        response_directives=directives,
    )


def build_scope_prompt(scope: BuildRequestScope) -> str:
    directives = "\n".join(f"- {directive}" for directive in scope.response_directives)
    target = scope.activity or "general play"
    if scope.encounter:
        target = f"{scope.encounter} in {target}"
    return (
        "BUILD REQUEST PLANNER (routing context, not factual evidence):\n"
        f"- Request breadth: {scope.kind}\n"
        f"- Build objective: {scope.objective}\n"
        f"- Activity or encounter: {target}\n"
        f"- Subjective superlative: {'yes' if scope.subjective_superlative else 'no'}\n"
        f"- Current popularity requested: {'yes' if scope.asks_for_popularity else 'no'}\n"
        f"{directives}"
    )


def _objective(normalized: str, interpreted: InterpretedQuestion) -> str:
    constrained_role = interpreted.constraints.get("role")
    if isinstance(constrained_role, str):
        return "weapon DPS" if constrained_role == "dps" else constrained_role
    for objective, aliases in _OBJECTIVES:
        if any(_contains_phrase(normalized, alias) for alias in aliases):
            return objective
    return "general build"


def _activity(normalized: str, interpreted: InterpretedQuestion) -> str | None:
    if interpreted.constraints.get("activity_mode") == "Dark Zone":
        return "Dark Zone"
    for activity, aliases in _ACTIVITY_ALIASES:
        if any(_contains_phrase(normalized, alias) for alias in aliases):
            return activity
    return None


def _retrieval_queries(
    *,
    normalized: str,
    current_game_version: str,
    objective: str,
    activity: str | None,
    encounter: str | None,
    kind: BuildRequestKind,
) -> tuple[str, ...]:
    values = [normalized]
    if kind == "broad":
        values.extend(
            (
                f"{current_game_version} current {objective} build decision matrix",
                f"{current_game_version} {objective} community meta popular configurations",
                f"{objective} sustained burst multi-target precision build alternatives",
            )
        )
    if activity:
        values.extend(
            (
                f"{activity} {current_game_version} recommended builds and community roles",
                f"{activity} progression team composition role build matrix encounter swaps",
            )
        )
    if encounter:
        values.append(f"{encounter} {activity or ''} role build skills mechanics")
    return _unique(values)


def _response_directives(
    *,
    kind: BuildRequestKind,
    objective: str,
    activity: str | None,
    subjective: bool,
) -> tuple[str, ...]:
    directives = [
        "Treat theoretical peak damage, realistic uptime, survivability, team utility, and "
        "item accessibility as separate selection criteria.",
        "Label community usage as a community signal and experimental combinations as "
        "theorycraft; do not present either as a verified mechanic or universal ranking.",
    ]
    if kind == "broad":
        directives.extend(
            (
                f"Give a practical current {objective} baseline before asking follow-up questions; "
                "do not stop at saying that 'best' is subjective.",
                "When evidence permits, offer two to four meaningfully different candidates, "
                "name what each optimizes, choose a practical default, and suggest one legal "
                "high-yield experiment.",
                "End with one optional narrowing question about content, solo/group play, "
                "weapon preference, or owned items only when the answer would materially change.",
            )
        )
    if kind == "activity":
        directives.extend(
            (
                f"Build for {activity or 'the resolved activity'} mechanics rather than for a "
                "shooting-range maximum.",
                "Give a readable role/build matrix with each role's purpose, core build, skills, "
                "and encounter swap points. Distinguish a progression/first-clear plan from an "
                "experienced optimization when current evidence supports both.",
                "If the member named one role, prioritize that loadout while explaining how it "
                "interlocks with the rest of the team.",
            )
        )
    if subjective:
        directives.append(
            "State the assumed definition of 'best' in one sentence, then make a conditional "
            "recommendation instead of claiming a universal winner."
        )
    return tuple(directives)


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(normalize_text(phrase))}(?!\w)", text) is not None


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            output.append(" ".join(value.split()))
    return tuple(output)
