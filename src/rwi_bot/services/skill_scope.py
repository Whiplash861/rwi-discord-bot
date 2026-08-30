from __future__ import annotations

import re
from dataclasses import dataclass

from rwi_bot.services.language import normalize_text

SKILL_TAXONOMY_VERSION = "Y8S3 Red Horizon"


@dataclass(frozen=True, slots=True)
class SkillVariant:
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillFamily:
    name: str
    member_label: str
    aliases: tuple[str, ...]
    variants: tuple[SkillVariant, ...]


@dataclass(frozen=True, slots=True)
class SkillFamilyRequest:
    family: SkillFamily
    explicitly_requests_all: bool = False

    @property
    def variant_names(self) -> tuple[str, ...]:
        return tuple(variant.name for variant in self.family.variants)


# Current platform/variant taxonomy. It is deliberately stats-free: values still need
# current verified knowledge or sufficiently strong external evidence before ERIN may answer.
SKILL_FAMILIES: tuple[SkillFamily, ...] = (
    SkillFamily(
        name="Pulse",
        member_label="Pulse",
        aliases=("pulse",),
        variants=(
            SkillVariant("Scanner Pulse", ("scanner",)),
            SkillVariant("Remote Pulse", ("remote",)),
            SkillVariant("Jammer Pulse", ("jammer",)),
            SkillVariant("Banshee Pulse", ("banshee",)),
            SkillVariant("Achilles Pulse", ("achilles",)),
        ),
    ),
    SkillFamily(
        name="Turret",
        member_label="Turret",
        aliases=("turret",),
        variants=(
            SkillVariant("Assault Turret", ("assault",)),
            SkillVariant("Incinerator Turret", ("incinerator", "flame turret")),
            SkillVariant("Sniper Turret", ("sniper",)),
            SkillVariant("Artillery Turret", ("artillery", "mortar turret")),
        ),
    ),
    SkillFamily(
        name="Seeker Mine",
        member_label="Seeker Mine",
        aliases=("seeker mine", "seeker", "seekers"),
        variants=(
            SkillVariant("Explosive Seeker Mine", ("explosive seeker",)),
            SkillVariant("Airburst Seeker Mine", ("airburst",)),
            SkillVariant("Cluster Seeker Mine", ("cluster",)),
            SkillVariant("Mender Seeker Mine", ("mender",)),
        ),
    ),
    SkillFamily(
        name="Ballistic Shield",
        member_label="Shield",
        aliases=("ballistic shield", "shield", "shields"),
        variants=(
            SkillVariant("Bulwark Shield", ("bulwark",)),
            SkillVariant("Crusader Shield", ("crusader",)),
            SkillVariant("Deflector Shield", ("deflector",)),
            SkillVariant("Striker Shield", ("striker shield",)),
        ),
    ),
    SkillFamily(
        name="Chem Launcher",
        member_label="Chem Launcher",
        aliases=("chem launcher", "chemical launcher", "chem"),
        variants=(
            SkillVariant("Reinforcer Chem Launcher", ("reinforcer",)),
            SkillVariant("Firestarter Chem Launcher", ("firestarter",)),
            SkillVariant("Riot Foam Chem Launcher", ("riot foam", "foam")),
            SkillVariant("Oxidizer Chem Launcher", ("oxidizer", "oxidiser")),
        ),
    ),
    SkillFamily(
        name="Drone",
        member_label="Drone",
        aliases=("drone", "drones"),
        variants=(
            SkillVariant("Striker Drone", ("striker drone",)),
            SkillVariant("Defender Drone", ("defender",)),
            SkillVariant("Bombardier Drone", ("bombardier",)),
            SkillVariant("Fixer Drone", ("fixer",)),
            SkillVariant("Tactician Drone", ("tactician",)),
        ),
    ),
    SkillFamily(
        name="Firefly",
        member_label="Firefly",
        aliases=("firefly",),
        variants=(
            SkillVariant("Blinder Firefly", ("blinder",)),
            SkillVariant("Burster Firefly", ("burster",)),
            SkillVariant("Demolisher Firefly", ("demolisher",)),
        ),
    ),
    SkillFamily(
        name="Hive",
        member_label="Hive",
        aliases=("hive", "hives"),
        variants=(
            SkillVariant("Restorer Hive", ("restorer",)),
            SkillVariant("Stinger Hive", ("stinger",)),
            SkillVariant("Reviver Hive", ("reviver",)),
            SkillVariant("Booster Hive", ("booster",)),
            SkillVariant("Artificer Hive", ("artificer",)),
        ),
    ),
    SkillFamily(
        name="Sticky Bomb",
        member_label="Sticky Bomb",
        aliases=("sticky bomb", "sticky"),
        variants=(
            SkillVariant("Explosive Sticky Bomb", ("explosive sticky",)),
            SkillVariant("Burn Sticky Bomb", ("burn sticky", "fire sticky")),
            SkillVariant("EMP Sticky Bomb", ("emp sticky",)),
        ),
    ),
    SkillFamily(
        name="Trap",
        member_label="Trap",
        aliases=("trap", "traps"),
        variants=(
            SkillVariant("Shock Trap", ("shock",)),
            SkillVariant("Repair Trap", ("repair",)),
            SkillVariant("Shrapnel Trap", ("shrapnel",)),
        ),
    ),
    SkillFamily(
        name="Smart Cover",
        member_label="Smart Cover",
        aliases=("smart cover",),
        variants=(
            SkillVariant("Fortified Smart Cover", ("fortified",)),
            SkillVariant("Precision Smart Cover", ("precision",)),
        ),
    ),
    SkillFamily(
        name="Decoy",
        member_label="Decoy",
        aliases=("decoy",),
        variants=(SkillVariant("Holographic Distraction Decoy", ("holographic",)),),
    ),
)

_ALL_VARIANTS = re.compile(
    r"\b(?:all|every|each)\b|\b(?:variants?|versions?|types?)\b",
    re.IGNORECASE,
)


def identify_broad_skill_family(question: str) -> SkillFamilyRequest | None:
    normalized = normalize_text(question)
    for family in SKILL_FAMILIES:
        if len(family.variants) < 2 or not _contains_any(normalized, family.aliases):
            continue
        if any(
            _contains_any(normalized, (variant.name, *variant.aliases))
            for variant in family.variants
        ):
            return None
        return SkillFamilyRequest(
            family=family,
            explicitly_requests_all=_ALL_VARIANTS.search(normalized) is not None,
        )
    return None


def skill_scope_prompt(request: SkillFamilyRequest) -> str:
    variants = ", ".join(request.variant_names)
    return (
        f"Broad skill family: {request.family.name}. Current variants that define a complete "
        f"family answer: {variants}. List every variant explicitly only if the evidence "
        "confidently supports all of them; never silently answer for just one variant."
    )


def response_covers_every_variant(text: str, request: SkillFamilyRequest) -> bool:
    normalized = normalize_text(text)
    return all(_contains_any(normalized, (variant.name,)) for variant in request.family.variants)


def render_variant_clarification(request: SkillFamilyRequest) -> str:
    names = [variant.name for variant in request.family.variants]
    joined = ", ".join(names[:-1]) + f", or {names[-1]}"
    if request.explicitly_requests_all:
        return (
            f"I can't confidently verify a complete current comparison for every "
            f"{request.family.member_label} variant yet. Which one should I narrow this to: "
            f"{joined}?"
        )
    return (
        f"{request.family.member_label} has multiple variants, and I can't confidently apply "
        f"one variant's values to the whole skill family. Which one do you mean: {joined}? "
        f"You can also say “all {request.family.member_label} variants” for a full comparison."
    )


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(normalize_text(candidate))}(?!\w)", text) is not None
        for candidate in candidates
    )
