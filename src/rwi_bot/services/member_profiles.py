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


@dataclass(frozen=True, slots=True)
class MemberAnswerProfile:
    assumptions: AnswerAssumptions
    detail_tier: AnswerTier = AnswerTier.STANDARD
    persisted: bool = False


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
_MODE = re.compile(
    r"\b(?:my(?:\s+default)?\s+mode\s*(?:is|=|:)|"
    r"i\s+(?:mostly\s+)?play|"
    r"set\s+(?:my\s+)?(?:default\s+)?mode\s+to)\s*(pve|pvp)\b",
    re.IGNORECASE,
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
    clean = _normalize(text)
    spans: list[tuple[int, int]] = []
    rejected: list[str] = []
    values: dict[str, object] = {}

    if _NUMERIC_DECLARATION.search(clean):
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
        values["mode"] = match.group(1).upper().replace("VE", "vE").replace("VP", "vP")
        spans.append(match.span())
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

    if not values and not rejected:
        return None
    raw_detail_tier = values.get("detail_tier")
    detail_tier = raw_detail_tier if isinstance(raw_detail_tier, AnswerTier) else None
    update = MemberProfileUpdate(
        level=_optional_int(values.get("level")),
        shd=_optional_int(values.get("shd")),
        expertise=_optional_int(values.get("expertise")),
        mode=_optional_str(values.get("mode")),
        maximum_item_rolls=_optional_bool(values.get("maximum_item_rolls")),
        include_conditional_buffs=_optional_bool(values.get("include_conditional_buffs")),
        detail_tier=detail_tier,
    )
    return InferredMemberProfileUpdate(
        update=update,
        profile_only=_is_profile_only(clean, spans),
        rejected=tuple(rejected),
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
        (
            heading,
            "",
            f"- Level {assumptions.level}",
            f"- SHD {assumptions.shd}",
            f"- Expertise {assumptions.expertise}",
            f"- {assumptions.mode}",
            f"- {roll_text}",
            f"- {conditional_text}",
            f"- {profile.detail_tier.value.title()} answer detail",
        )
    )


def _normalize(text: str) -> str:
    normalized = (
        unicodedata.normalize("NFKC", text)
        .replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
        .casefold()
    )
    return re.sub(r"\s+", " ", normalized).strip()


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
