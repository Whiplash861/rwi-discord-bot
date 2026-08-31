from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rwi_bot.domain.schemas import AnswerAssumptions, AnswerTier


@dataclass(frozen=True, slots=True)
class MemberProfileUpdate:
    level: int | None = None
    shd: int | None = None
    expertise: int | None = None
    mode: str | None = None
    platforms: tuple[str, ...] | None = None
    gamertag: str | None = None
    preferred_playstyle: str | None = None
    profile_notes_add: tuple[str, ...] | None = None
    profile_notes_remove: tuple[str, ...] | None = None
    maximum_item_rolls: bool | None = None
    include_conditional_buffs: bool | None = None
    detail_tier: AnswerTier | None = None

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, value in (
                ("level", self.level),
                ("shd", self.shd),
                ("expertise", self.expertise),
                ("mode", self.mode),
                ("platforms", self.platforms),
                ("gamertag", self.gamertag),
                ("preferred_playstyle", self.preferred_playstyle),
                ("profile_notes_add", self.profile_notes_add),
                ("profile_notes_remove", self.profile_notes_remove),
                ("maximum_item_rolls", self.maximum_item_rolls),
                ("include_conditional_buffs", self.include_conditional_buffs),
                ("detail_tier", self.detail_tier),
            )
            if value is not None
        )


@dataclass(frozen=True, slots=True)
class InferredMemberProfileUpdate:
    update: MemberProfileUpdate
    profile_only: bool
    rejected: tuple[str, ...] = ()
    sensitive_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MemberAnswerProfile:
    assumptions: AnswerAssumptions
    detail_tier: AnswerTier = AnswerTier.STANDARD
    persisted: bool = False
    gamertag: str | None = None


_NUMERIC_DECLARATION = re.compile(
    r"(?:\b(?:i am|i'm|im)\s+(?:currently\s+)?(?:at\s+)?"
    r"(?:shd|expertise|level)\b|"
    r"\bmy\s+(?:shd|expertise|character\s+level|level)\b|"
    r"\b(?:set|update|change)\s+(?:me|my(?:\s+profile)?)\b|"
    r"\bremember(?:\s+that)?\s+(?:i|my)\b)",
    re.IGNORECASE,
)
_SHD = re.compile(r"\bshd(?:\s+level)?\s*(?:is|=|:|to|at)?\s*(\d{1,7})\b", re.IGNORECASE)
_EXPERTISE = re.compile(
    r"\bexpertise(?:\s+level)?\s*(?:is|=|:|to|at)?\s*(\d{1,3})\b",
    re.IGNORECASE,
)
_LEVEL = re.compile(
    r"(?<!shd )\b(?:character\s+)?level\s*(?:is|=|:|to|at)?\s*(\d{1,3})\b",
    re.IGNORECASE,
)
_PROFILE_NUMERIC_LIST = re.compile(r"^\s*(?:shd|expertise|(?:character\s+)?level)\b", re.IGNORECASE)
_MODE = re.compile(
    r"\b(?:my(?:\s+default)?\s+mode\s*(?:is|=|:)|"
    r"i\s+(?:mostly\s+)?play|"
    r"set\s+(?:my\s+)?(?:default\s+)?mode\s+to)\s*(pve|pvp|both)\b",
    re.IGNORECASE,
)
_PLATFORMS = re.compile(
    r"\b(?:i\s+play\s+on|my\s+platforms?\s*(?:is|are|=|:)|platforms?\s*[:=])\s*"
    r"((?:xbox|pc|playstation|ps4|ps5)(?:\s*(?:,|/|&|and)\s*"
    r"(?:xbox|pc|playstation|ps4|ps5))*)\b",
    re.IGNORECASE,
)
_GAMERTAG = re.compile(
    r"\b(?:my\s+)?(?:gamertag|ubisoft(?:\s+connect)?\s+name|in[- ]game\s+name)\s*"
    r"(?:is|=|:)\s*([a-z0-9][a-z0-9 _#.-]{1,31}?)"
    r"(?=\s+(?:and\s+)?(?:i\s+play\b|my\s+(?:platform|preferred)|platform\b|"
    r"shd\b|expertise\b|pve\b|pvp\b)|[.!?]|$)",
    re.IGNORECASE,
)
_PLAYSTYLE = re.compile(
    r"\b(?:my\s+)?(?:preferred\s+)?playstyle\s*(?:is|=|:)\s*"
    r"([a-z0-9][a-z0-9 ,/'&+_-]{1,119}?)"
    r"(?=\s+(?:and\s+)?(?:my\s+)?(?:platform|gamertag|shd|expertise|mode)\b|[.!?]|$)",
    re.IGNORECASE,
)
_EXPLICIT_PROFILE_NOTE = re.compile(
    r"\b(?:add|save|note|put|remember)(?:\s+this)?\s+"
    r"(?:to|in|on|for)?\s*(?:my\s+)?(?:erin\s+)?profile\s*(?::|that|=)?\s*"
    r"(.{2,300})$",
    re.IGNORECASE,
)
_REMOVE_PROFILE_NOTE = re.compile(
    r"\b(?:remove|delete|forget|strike)(?:\s+the\s+fact)?(?:\s+that)?\s+"
    r"(?:from\s+my\s+(?:erin\s+)?profile\s*)?(.{2,200})$",
    re.IGNORECASE,
)
_EXPERIENCE_NOTE = re.compile(
    r"\b(?:i\s+am|i'm|im)\s+(?:an?\s+)?"
    r"(beta\s+tester|day[ -]one\s+player|veteran\s+player|returning\s+player)\b",
    re.IGNORECASE,
)
_DAY_ONE_NOTE = re.compile(
    r"\b(?:i\s+am|i'm|im)\b.{0,80}\bday[ -]one\s+player\b",
    re.IGNORECASE,
)
_DAY_ONE_PHRASE = re.compile(r"\bday[ -]one\s+player\b", re.IGNORECASE)
_MAIN_NOTE = re.compile(
    r"\b(?:i\s+main|i\s+am|i'm|im)\s+(?:an?\s+)?"
    r"(healer|support|tank|dps|sniper|skill|status)(?:\s+(?:main|player))?\b",
    re.IGNORECASE,
)
_PREFERENCE_NOTE = re.compile(
    r"\bi\s+(like|love|prefer|dislike|hate|do\s+not\s+like|don't\s+like)\s+"
    r"([a-z0-9][a-z0-9 /'&+_-]{1,100}?)(?=[.!?]|$)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")
_SENSITIVE_LABELS = (
    ("real name", re.compile(r"\b(?:my\s+)?(?:real|legal|full)\s+name\b", re.IGNORECASE)),
    ("birthday", re.compile(r"\b(?:birthday|date\s+of\s+birth|dob)\b", re.IGNORECASE)),
    ("phone number", re.compile(r"\b(?:phone|mobile|cell)\s+(?:number|#)\b", re.IGNORECASE)),
    ("home address", re.compile(r"\b(?:home|street|mailing)\s+address\b", re.IGNORECASE)),
    ("email address", re.compile(r"\b(?:personal\s+)?email(?:\s+address)?\b", re.IGNORECASE)),
)
_DETAIL_TIER = re.compile(
    r"\b(?:i\s+prefer|my\s+(?:answer\s+)?detail\s+(?:is|=)|"
    r"set\s+my\s+(?:answer\s+)?detail\s+to)\s*"
    r"(concise|standard|technical)(?:\s+answers?)?\b",
    re.IGNORECASE,
)
_MAX_ROLLS_FALSE = re.compile(
    r"\b(?:do\s+not|don't|never)\s+(?:assume|use)\s+"
    r"(?:maximum|max)(?:\s+item)?\s+rolls\s+"
    r"(?:by\s+default|for\s+future\s+answers?|for\s+my\s+answers?)\b",
    re.IGNORECASE,
)
_MAX_ROLLS_TRUE = re.compile(
    r"\b(?:always\s+)?(?:assume|use)\s+(?:maximum|max)(?:\s+item)?\s+rolls\s+"
    r"(?:by\s+default|for\s+future\s+answers?|for\s+my\s+answers?)\b",
    re.IGNORECASE,
)
_CONDITIONAL_FALSE = re.compile(
    r"\b(?:always\s+)?(?:exclude|do\s+not\s+include|don't\s+include)\s+"
    r"conditional\s+buffs\s+(?:by\s+default|for\s+future\s+answers?|"
    r"for\s+my\s+answers?)\b",
    re.IGNORECASE,
)
_CONDITIONAL_TRUE = re.compile(
    r"\b(?:always\s+)?include\s+conditional\s+buffs\s+"
    r"(?:by\s+default|for\s+future\s+answers?|for\s+my\s+answers?)\b",
    re.IGNORECASE,
)

_PROFILE_QUERY = re.compile(
    r"^\s*(?:show|tell)\s+me\s+(?:my|what\s+you\s+(?:know|remember)\s+about\s+my)\s+"
    r"(?:erin\s+)?profile\s*[?.!]*\s*$|"
    r"^\s*(?:what(?:'s|\s+is)|show)\s+my\s+(?:erin\s+)?"
    r"(?:profile|settings|assumptions)\s*[?.!]*\s*$|"
    r"^\s*what\s+do\s+you\s+(?:know|remember)\s+about\s+me\s*[?.!]*\s*$",
    re.IGNORECASE,
)

_PROFILE_FILLER = re.compile(
    r"\b(?:i'm|im|i|am|my|me|profile|set|update|change|remember|that|currently|"
    r"at|to|is|and|also|please|thanks|thank\s+you|erin|for\s+future\s+answers?|"
    r"from\s+now\s+on)\b",
    re.IGNORECASE,
)


def infer_member_profile_update(text: str) -> InferredMemberProfileUpdate | None:
    clean = _normalize_preserving_case(text)
    spans: list[tuple[int, int]] = []
    rejected: list[str] = []
    values: dict[str, object] = {}
    sensitive_flags = detect_possible_personal_information(clean)

    if (
        _NUMERIC_DECLARATION.search(clean)
        or _PROFILE_NUMERIC_LIST.search(clean)
        or _PLATFORMS.search(clean)
        or _GAMERTAG.search(clean)
        or _PLAYSTYLE.search(clean)
    ):
        _extract_number(
            clean,
            _SHD,
            field="shd",
            minimum=0,
            maximum=1_000_000,
            spans=spans,
            values=values,
            rejected=rejected,
            label="SHD level",
        )
        _extract_number(
            clean,
            _EXPERTISE,
            field="expertise",
            minimum=0,
            maximum=30,
            spans=spans,
            values=values,
            rejected=rejected,
            label="Expertise",
        )
        _extract_number(
            clean,
            _LEVEL,
            field="level",
            minimum=1,
            maximum=40,
            spans=spans,
            values=values,
            rejected=rejected,
            label="character level",
        )

    if match := _last_match(_MODE, clean):
        mode = match.group(1).casefold()
        values["mode"] = {"pve": "PvE", "pvp": "PvP", "both": "Both"}[mode]
        spans.append(match.span())
    if match := _last_match(_PLATFORMS, clean):
        platforms = tuple(
            platform
            for platform in ("Xbox", "PC", "PS")
            if platform in _canonical_platforms(match.group(1))
        )
        if platforms:
            values["platforms"] = platforms
            spans.append(match.span())
    if match := _last_match(_GAMERTAG, clean):
        values["gamertag"] = _clean_free_text(match.group(1), maximum=32)
        spans.append(match.span())
    if match := _last_match(_PLAYSTYLE, clean):
        values["preferred_playstyle"] = _clean_free_text(match.group(1), maximum=120)
        spans.append(match.span())
    profile_notes: list[str] = []
    notes_to_remove: list[str] = []
    if match := _last_match(_REMOVE_PROFILE_NOTE, clean):
        notes_to_remove.append(_canonical_note_removal(match.group(1)))
        spans.append(match.span())
    elif match := _last_match(_EXPLICIT_PROFILE_NOTE, clean):
        if not sensitive_flags:
            profile_notes.append(_clean_free_text(match.group(1), maximum=300))
        spans.append(match.span())
    if not sensitive_flags and not notes_to_remove:
        for match in _EXPERIENCE_NOTE.finditer(clean):
            profile_notes.append(f"Experience: {_clean_free_text(match.group(1), maximum=80)}")
            spans.append(match.span())
        if _DAY_ONE_NOTE.search(clean) and (match := _DAY_ONE_PHRASE.search(clean)):
            profile_notes.append("Experience: day-one player")
            spans.append(match.span())
        for match in _MAIN_NOTE.finditer(clean):
            profile_notes.append(
                f"Main role/playstyle: {_clean_free_text(match.group(1), maximum=80)}"
            )
            spans.append(match.span())
        for match in _PREFERENCE_NOTE.finditer(clean):
            sentiment = _clean_free_text(match.group(1), maximum=24).casefold()
            subject = _clean_free_text(match.group(2), maximum=100)
            label = "Likes/prefers" if sentiment in {"like", "love", "prefer"} else "Dislikes"
            profile_notes.append(f"{label}: {subject}")
            spans.append(match.span())
    if profile_notes:
        values["profile_notes_add"] = tuple(dict.fromkeys(profile_notes))
    if notes_to_remove:
        values["profile_notes_remove"] = tuple(dict.fromkeys(notes_to_remove))
    if match := _last_match(_DETAIL_TIER, clean):
        values["detail_tier"] = AnswerTier(match.group(1).casefold())
        spans.append(match.span())

    boolean_patterns = (
        ("maximum_item_rolls", False, _MAX_ROLLS_FALSE),
        ("maximum_item_rolls", True, _MAX_ROLLS_TRUE),
        ("include_conditional_buffs", False, _CONDITIONAL_FALSE),
        ("include_conditional_buffs", True, _CONDITIONAL_TRUE),
    )
    for field, value, pattern in boolean_patterns:
        if match := pattern.search(clean):
            values[field] = value
            spans.append(match.span())

    if not values and not rejected and not sensitive_flags:
        return None
    raw_detail_tier = values.get("detail_tier")
    detail_tier = raw_detail_tier if isinstance(raw_detail_tier, AnswerTier) else None
    update = MemberProfileUpdate(
        level=_optional_int(values.get("level")),
        shd=_optional_int(values.get("shd")),
        expertise=_optional_int(values.get("expertise")),
        mode=_optional_str(values.get("mode")),
        platforms=_optional_tuple(values.get("platforms")),
        gamertag=_optional_str(values.get("gamertag")),
        preferred_playstyle=_optional_str(values.get("preferred_playstyle")),
        profile_notes_add=_optional_tuple(values.get("profile_notes_add")),
        profile_notes_remove=_optional_tuple(values.get("profile_notes_remove")),
        maximum_item_rolls=_optional_bool(values.get("maximum_item_rolls")),
        include_conditional_buffs=_optional_bool(values.get("include_conditional_buffs")),
        detail_tier=detail_tier,
    )
    return InferredMemberProfileUpdate(
        update=update,
        profile_only=_is_profile_only(clean, spans),
        rejected=tuple(rejected),
        sensitive_flags=sensitive_flags,
    )


def is_profile_query(text: str) -> bool:
    return _PROFILE_QUERY.fullmatch(_normalize(text)) is not None


def render_member_profile(profile: MemberAnswerProfile, *, updated: bool = False) -> str:
    assumptions = profile.assumptions
    if updated:
        heading = "Updated your ERIN profile. I'll use these settings when you message me:"
    elif profile.persisted:
        heading = "Your saved ERIN profile:"
    else:
        heading = "You don't have custom ERIN settings saved yet. Current defaults:"
    roll_text = "maximum item rolls" if assumptions.maximum_item_rolls else "current item rolls"
    conditional_text = (
        "conditional buffs included"
        if assumptions.include_conditional_buffs
        else "conditional buffs excluded unless requested"
    )
    return "\n".join(
        tuple(
            line
            for line in (
                heading,
                "",
                f"- Platforms: {', '.join(assumptions.platforms)}"
                if assumptions.platforms
                else None,
                f"- Gamertag: {profile.gamertag}" if profile.gamertag else None,
                f"- Level {assumptions.level}",
                f"- SHD {assumptions.shd}",
                f"- Expertise {assumptions.expertise}",
                f"- Focus: {assumptions.mode}",
                (
                    f"- Preferred playstyle: {assumptions.preferred_playstyle}"
                    if assumptions.preferred_playstyle
                    else None
                ),
                (
                    "- Personal notes: " + "; ".join(assumptions.profile_notes)
                    if assumptions.profile_notes
                    else None
                ),
                f"- {roll_text}",
                f"- {conditional_text}",
                f"- {profile.detail_tier.value.title()} answer detail",
            )
            if line is not None
        )
    )


def _normalize(text: str) -> str:
    return _normalize_preserving_case(text).casefold()


def _normalize_preserving_case(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
    return re.sub(r"\s+", " ", normalized).strip()


def _canonical_platforms(value: str) -> set[str]:
    platforms: set[str] = set()
    lowered = value.casefold()
    if "xbox" in lowered:
        platforms.add("Xbox")
    if re.search(r"\bpc\b", lowered):
        platforms.add("PC")
    if re.search(r"\b(?:playstation|ps4|ps5)\b", lowered):
        platforms.add("PS")
    return platforms


def _clean_free_text(value: str, *, maximum: int) -> str:
    return " ".join(value.split()).strip(" .,!?:;")[:maximum]


def _canonical_note_removal(value: str) -> str:
    clean = _clean_free_text(value, maximum=200)
    if match := _PREFERENCE_NOTE.fullmatch(clean):
        sentiment = _clean_free_text(match.group(1), maximum=24).casefold()
        subject = _clean_free_text(match.group(2), maximum=100)
        label = "Likes/prefers" if sentiment in {"like", "love", "prefer"} else "Dislikes"
        return f"{label}: {subject}"
    if match := _MAIN_NOTE.fullmatch(clean):
        return f"Main role/playstyle: {_clean_free_text(match.group(1), maximum=80)}"
    return clean


def detect_possible_personal_information(text: str) -> tuple[str, ...]:
    flags = [label for label, pattern in _SENSITIVE_LABELS if pattern.search(text)]
    if _EMAIL.search(text) and "email address" not in flags:
        flags.append("email address")
    if _PHONE.search(text) and "phone number" not in flags:
        flags.append("phone number")
    return tuple(flags)


def _extract_number(
    text: str,
    pattern: re.Pattern[str],
    *,
    field: str,
    minimum: int,
    maximum: int,
    spans: list[tuple[int, int]],
    values: dict[str, object],
    rejected: list[str],
    label: str,
) -> None:
    match = _last_match(pattern, text)
    if match is None:
        return
    spans.append(match.span())
    value = int(match.group(1))
    if minimum <= value <= maximum:
        values[field] = value
    else:
        rejected.append(f"{label} must be between {minimum} and {maximum}.")


def _last_match(pattern: re.Pattern[str], text: str) -> re.Match[str] | None:
    matches = list(pattern.finditer(text))
    return matches[-1] if matches else None


def _is_profile_only(text: str, spans: list[tuple[int, int]]) -> bool:
    remainder = text
    for start, end in sorted(spans, reverse=True):
        remainder = f"{remainder[:start]} {remainder[end:]}"
    remainder = _PROFILE_FILLER.sub(" ", remainder)
    remainder = re.sub(r"[^a-z0-9]+", " ", remainder).strip()
    return not remainder


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_tuple(value: object) -> tuple[str, ...] | None:
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return value
    return None
