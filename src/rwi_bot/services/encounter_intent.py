from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from rwi_bot.services.language import normalize_text


@dataclass(frozen=True, slots=True)
class EncounterEntity:
    name: str
    activity: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ActivityEntity:
    name: str
    activity_type: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EncounterPrediction:
    activity: str | None
    encounter: str | None
    request_kind: str
    confidence: float
    search_query: str
    clarification: str | None = None


ACTIVITIES: tuple[ActivityEntity, ...] = (
    ActivityEntity(
        "Paradise Lost",
        "Incursion",
        ("paradise lost", "meret estate", "merit estate", "meret state"),
    ),
    ActivityEntity(
        "Broken Rain",
        "Incursion",
        (
            "broken rain",
            "broken reign",
            "brocken rain",
            "steel creek dam",
            "steel creek",
            "the dam",
            "hydroelectric plant",
        ),
    ),
    ActivityEntity(
        "Operation Dark Hours",
        "Raid",
        ("operation dark hours", "dark hours", "odh", "airport raid"),
    ),
    ActivityEntity(
        "Operation Iron Horse",
        "Raid",
        ("operation iron horse", "iron horse", "ih raid", "foundry raid"),
    ),
)


ENCOUNTERS: tuple[EncounterEntity, ...] = (
    EncounterEntity(
        "Estate Turrets",
        "Paradise Lost",
        ("estate turrets", "turrets", "estate defenses", "first encounter"),
    ),
    EncounterEntity(
        "Oil Tanker Defense",
        "Paradise Lost",
        ("oil tanker", "tanker defense", "tanker", "second encounter"),
    ),
    EncounterEntity(
        "Wright",
        "Paradise Lost",
        ("wright", "flaming hunter", "fire hunter"),
    ),
    EncounterEntity(
        "The Lovebirds: Martinez and Johnson",
        "Paradise Lost",
        (
            "lovebirds",
            "love birds",
            "the lovebirds",
            "martinez and johnson",
            "johnson and martinez",
            "martinez",
            "johnson",
            "final boss",
        ),
    ),
    EncounterEntity("Lester Steel", "Broken Rain", ("lester steel", "lester")),
    EncounterEntity(
        "Patch Escort and Dwayne Steel IV",
        "Broken Rain",
        (
            "patch escort",
            "warhound escort",
            "war hound escort",
            "dwayne steel iv",
            "dwayne steel",
            "dwayne",
        ),
    ),
    EncounterEntity("Iris Steel", "Broken Rain", ("iris steel", "iris")),
    EncounterEntity(
        "Marguerite Steel",
        "Broken Rain",
        (
            "marguerite steel",
            "margaret steel",
            "marguerite",
            "margaret",
            "final boss",
        ),
    ),
    EncounterEntity(
        "Max 'Boomer' Bailey",
        "Operation Dark Hours",
        ("max boomer bailey", "boomer bailey", "boomer"),
    ),
    EncounterEntity(
        "Dizzy, Ricochet, and Weasel",
        "Operation Dark Hours",
        ("dizzy ricochet and weasel", "dizzy ricochet weasel", "weasel"),
    ),
    EncounterEntity(
        "Buddy and Lucy",
        "Operation Dark Hours",
        ("buddy and lucy", "buddy lucy"),
    ),
    EncounterEntity(
        "DDP-52 Razorback",
        "Operation Dark Hours",
        ("ddp 52 razorback", "razorback", "final boss"),
    ),
    EncounterEntity(
        "Lieutenant Gray",
        "Operation Iron Horse",
        ("lieutenant gray", "lt gray", "gray"),
    ),
    EncounterEntity(
        "Captain Fieser",
        "Operation Iron Horse",
        ("captain fieser", "fieser", "feiser"),
    ),
    EncounterEntity(
        "Lieutenant Williams",
        "Operation Iron Horse",
        ("lieutenant williams", "lt williams", "williams"),
    ),
    EncounterEntity(
        "Colonel Morozova and the Iron Horse",
        "Operation Iron Horse",
        (
            "colonel morozova",
            "morozova",
            "iron horse train",
            "final train",
            "final boss",
        ),
    ),
)


_ENCOUNTER_LANGUAGE = (
    "beat",
    "defeat",
    "kill",
    "clear",
    "fight",
    "boss",
    "encounter",
    "mechanic",
    "strategy",
    "guide",
    "walkthrough",
    "incursion",
    "raid",
)

_BUILD_LANGUAGE = ("build", "loadout", "gear", "role", "setup", "composition")

_ENTITY_QUESTION_LANGUAGE = (
    *_ENCOUNTER_LANGUAGE,
    *_BUILD_LANGUAGE,
    "who is",
    "what is",
    "tell me about",
    "explain",
)

_FUZZY_STOP_WORDS = {
    "a",
    "all",
    "an",
    "and",
    "at",
    "beat",
    "boss",
    "build",
    "can",
    "clear",
    "complete",
    "defeat",
    "do",
    "encounter",
    "every",
    "fight",
    "for",
    "full",
    "gear",
    "guide",
    "how",
    "i",
    "in",
    "incursion",
    "kill",
    "loadout",
    "mechanic",
    "mechanics",
    "of",
    "raid",
    "role",
    "setup",
    "should",
    "strategy",
    "the",
    "to",
    "walkthrough",
    "we",
    "what",
    "who",
    "you",
}


def predict_encounter_request(question: str) -> EncounterPrediction | None:
    """Predict a canonical activity/encounter without treating a fuzzy guess as fact."""

    normalized = normalize_text(question)
    if not normalized:
        return None

    has_encounter_language = any(token in normalized for token in _ENCOUNTER_LANGUAGE)
    has_entity_question_language = any(token in normalized for token in _ENTITY_QUESTION_LANGUAGE)
    activity, activity_score = _exact_activity(normalized)
    encounter, encounter_score = _exact_encounter(
        normalized,
        activity,
        allow_ambiguous=has_entity_question_language,
    )

    if encounter is None and has_encounter_language:
        encounter, encounter_score, ambiguous_matches = _fuzzy_encounter(normalized, activity)
        if ambiguous_matches:
            activities = {item.activity for item in ambiguous_matches}
            activity_name = next(iter(activities)) if len(activities) == 1 else None
            options = ", ".join(f"**{item.name}**" for item in ambiguous_matches[:4])
            return EncounterPrediction(
                activity=activity_name,
                encounter=None,
                request_kind=_request_kind(normalized, has_activity=bool(activity_name)),
                confidence=encounter_score,
                search_query=normalized,
                clarification=(
                    f"I found more than one possible encounter: {options}. Which one do you mean?"
                ),
            )
        if encounter is not None and encounter_score < 0.84:
            return EncounterPrediction(
                activity=encounter.activity,
                encounter=None,
                request_kind=_request_kind(normalized, has_activity=bool(activity)),
                confidence=encounter_score,
                search_query=normalized,
                clarification=(
                    f"Did you mean **{encounter.name}** in **{encounter.activity}**? "
                    "If not, give me the activity and encounter name and I'll narrow it down."
                ),
            )

    if encounter is not None:
        activity = next(item for item in ACTIVITIES if item.name == encounter.activity)
        activity_score = max(activity_score, encounter_score)
    elif activity is None and has_encounter_language:
        activity, activity_score = _fuzzy_activity(normalized)
        if activity is not None and activity_score < 0.84:
            return EncounterPrediction(
                activity=None,
                encounter=None,
                request_kind=_request_kind(normalized, has_activity=False),
                confidence=activity_score,
                search_query=normalized,
                clarification=(
                    f"Did you mean **{activity.name}**, the {activity.activity_type}? "
                    "If not, tell me which Incursion or Raid you mean."
                ),
            )

    if activity is None and encounter is None:
        return None

    request_kind = _request_kind(normalized, has_activity=activity is not None)
    canonical_terms = [normalized]
    if activity is not None:
        canonical_terms.append(activity.name)
        canonical_terms.append(activity.activity_type)
    if encounter is not None:
        canonical_terms.append(encounter.name)
    if request_kind in {"encounter_guide", "activity_guide"}:
        canonical_terms.append("objective sequence mechanics failure wipe roles recommended builds")
    elif request_kind == "build_recommendation":
        canonical_terms.append("recommended builds roles skills encounter mechanics")

    return EncounterPrediction(
        activity=activity.name if activity is not None else None,
        encounter=encounter.name if encounter is not None else None,
        request_kind=request_kind,
        confidence=max(activity_score, encounter_score),
        search_query=" ".join(dict.fromkeys(canonical_terms)),
    )


def encounter_scope_prompt(prediction: EncounterPrediction) -> str:
    target = prediction.activity or "unknown activity"
    if prediction.encounter:
        target = f"{prediction.encounter} in {target}"
    return (
        "PREDICTIVE ENCOUNTER RESOLUTION (routing context, not evidence):\n"
        f"- Canonical target: {target}\n"
        f"- Request type: {prediction.request_kind}\n"
        f"- Resolver confidence: {prediction.confidence:.0%}\n"
        "Use the canonical target even if the member used a misspelling, shorthand, boss-only "
        "name, or alternate activity wording. For a guide, lead with the objective and team "
        "setup; give the intended mechanics in numbered order; name wipe/failure conditions; "
        "then give encounter-specific recommended builds, skills, and substitutions. Explain "
        "callouts in ordinary language and exclude skips, cheeses, bugs, and exploits."
    )


def _contains_alias(normalized: str, alias: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(normalize_text(alias))}(?!\w)", normalized) is not None


def _exact_activity(normalized: str) -> tuple[ActivityEntity | None, float]:
    matches = [
        item
        for item in ACTIVITIES
        if any(_contains_alias(normalized, alias) for alias in item.aliases)
    ]
    if not matches:
        return None, 0.0
    return max(matches, key=lambda item: max(map(len, item.aliases))), 0.99


def _exact_encounter(
    normalized: str,
    activity: ActivityEntity | None,
    *,
    allow_ambiguous: bool,
) -> tuple[EncounterEntity | None, float]:
    candidates = [item for item in ENCOUNTERS if activity is None or item.activity == activity.name]
    matches = []
    for item in candidates:
        matched_aliases = [alias for alias in item.aliases if _contains_alias(normalized, alias)]
        if not matched_aliases:
            continue
        if not allow_ambiguous and all(
            len(normalize_text(alias).split()) == 1 for alias in matched_aliases
        ):
            continue
        matches.append(item)
    if not matches:
        return None, 0.0
    if len({item.name for item in matches}) > 1:
        return None, 0.0
    return max(matches, key=lambda item: max(map(len, item.aliases))), 0.99


def _fuzzy_encounter(
    normalized: str, activity: ActivityEntity | None
) -> tuple[EncounterEntity | None, float, tuple[EncounterEntity, ...]]:
    candidates = [item for item in ENCOUNTERS if activity is None or item.activity == activity.name]
    fragment = _fuzzy_fragment(normalized, activity)
    if not fragment:
        return None, 0.0, ()
    scored = sorted(
        (
            (
                item,
                max(
                    fuzz.WRatio(fragment, normalize_text(alias))
                    for alias in (item.name, *item.aliases)
                ),
            )
            for item in candidates
        ),
        key=lambda value: value[1],
        reverse=True,
    )
    if not scored or scored[0][1] < 68:
        return None, 0.0, ()
    top_entity, top_score = scored[0]
    close_entities = [item for item, score in scored if top_score - score <= 3]
    if len(close_entities) > 1:
        return None, float(top_score) / 100.0, tuple(close_entities)
    return top_entity, float(top_score) / 100.0, ()


def _fuzzy_activity(normalized: str) -> tuple[ActivityEntity | None, float]:
    aliases = {
        normalize_text(alias): item for item in ACTIVITIES for alias in (item.name, *item.aliases)
    }
    fragment = " ".join(token for token in normalized.split() if token not in _FUZZY_STOP_WORDS)
    result = process.extractOne(fragment, aliases.keys(), scorer=fuzz.WRatio, score_cutoff=68)
    if result is None:
        return None, 0.0
    alias, score, _ = result
    return aliases[alias], float(score) / 100.0


def _fuzzy_fragment(normalized: str, activity: ActivityEntity | None) -> str:
    fragment = normalized
    if activity is not None:
        for alias in sorted((activity.name, *activity.aliases), key=len, reverse=True):
            fragment = re.sub(rf"(?<!\w){re.escape(normalize_text(alias))}(?!\w)", " ", fragment)
    return " ".join(token for token in fragment.split() if token not in _FUZZY_STOP_WORDS)


def _request_kind(normalized: str, *, has_activity: bool) -> str:
    if any(token in normalized for token in _BUILD_LANGUAGE):
        return "build_recommendation"
    if has_activity and any(token in normalized for token in ("all", "every", "full", "complete")):
        return "activity_guide"
    if any(token in normalized for token in _ENCOUNTER_LANGUAGE):
        return "encounter_guide"
    return "activity_overview" if has_activity else "encounter_overview"
