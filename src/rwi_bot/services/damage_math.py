from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Amplifier:
    name: str
    value: Decimal
    team_buff: bool = False


@dataclass(frozen=True, slots=True)
class DamageInputs:
    """Deterministic single-projectile weapon-hit inputs expressed as decimal rates."""

    base_damage: Decimal
    weapon_damage: Decimal = Decimal("0")
    weapon_type_damage: Decimal = Decimal("0")
    additive_weapon_damage: Decimal = Decimal("0")
    total_weapon_damage: Decimal = Decimal("0")
    headshot_damage: Decimal = Decimal("0")
    critical_hit_damage: Decimal = Decimal("0")
    critical_hit_chance: Decimal = Decimal("0")
    damage_to_armor: Decimal = Decimal("0")
    damage_to_health: Decimal = Decimal("0")
    damage_to_targets_out_of_cover: Decimal = Decimal("0")
    team_weapon_damage: Decimal = Decimal("0")
    team_total_weapon_damage: Decimal = Decimal("0")
    team_headshot_damage: Decimal = Decimal("0")
    team_critical_hit_damage: Decimal = Decimal("0")
    team_damage_to_armor: Decimal = Decimal("0")
    team_damage_to_health: Decimal = Decimal("0")
    team_damage_to_targets_out_of_cover: Decimal = Decimal("0")
    amplifiers: tuple[Amplifier, ...] = ()
    headshot: bool = False
    critical_hit: bool = False
    expected_critical_value: bool = False
    target_has_armor: bool = False
    target_has_health: bool = True
    target_out_of_cover: bool = False
    base_includes_weapon_damage_bucket: bool = False


@dataclass(frozen=True, slots=True)
class DamageStep:
    number: int
    name: str
    formula: str
    multiplier: Decimal
    result: Decimal
    applied: bool = True


@dataclass(frozen=True, slots=True)
class DamageBreakdown:
    inputs: DamageInputs
    steps: tuple[DamageStep, ...]
    final_damage: Decimal
    notes: tuple[str, ...] = field(default_factory=tuple)


def calculate_weapon_hit(inputs: DamageInputs) -> DamageBreakdown:
    _validate(inputs)
    running = inputs.base_damage
    steps: list[DamageStep] = [
        DamageStep(1, "Base weapon damage", f"{_number(running)}", Decimal("1"), running)
    ]

    weapon_bonus = (
        inputs.weapon_damage
        + inputs.weapon_type_damage
        + inputs.additive_weapon_damage
        + inputs.team_weapon_damage
    )
    weapon_multiplier = (
        Decimal("1") if inputs.base_includes_weapon_damage_bucket else (Decimal("1") + weapon_bonus)
    )
    running *= weapon_multiplier
    steps.append(
        DamageStep(
            2,
            "Weapon Damage bucket",
            (
                "already included in the supplied displayed weapon damage"
                if inputs.base_includes_weapon_damage_bucket
                else "1 + Weapon Damage + weapon-type damage + additive/team Weapon Damage "
                f"= {_number(weapon_multiplier)}"
            ),
            weapon_multiplier,
            running,
        )
    )

    total_weapon_bonus = inputs.total_weapon_damage + inputs.team_total_weapon_damage
    total_weapon_multiplier = Decimal("1") + total_weapon_bonus
    running *= total_weapon_multiplier
    steps.append(
        DamageStep(
            3,
            "Total Weapon Damage bucket",
            "1 + all active personal and team Total Weapon Damage bonuses "
            f"= {_number(total_weapon_multiplier)}",
            total_weapon_multiplier,
            running,
            applied=bool(total_weapon_bonus),
        )
    )

    headshot_bonus = (
        inputs.headshot_damage + inputs.team_headshot_damage if inputs.headshot else Decimal("0")
    )
    critical_pool = inputs.critical_hit_damage + inputs.team_critical_hit_damage
    if inputs.expected_critical_value:
        critical_bonus = inputs.critical_hit_chance * critical_pool
        critical_description = (
            "CHC \N{MULTIPLICATION SIGN} CHD for expected value "
            f"({_percent(inputs.critical_hit_chance)} "
            f"\N{MULTIPLICATION SIGN} {_percent(critical_pool)})"
        )
    elif inputs.critical_hit:
        critical_bonus = critical_pool
        critical_description = "full CHD for a confirmed critical hit"
    else:
        critical_bonus = Decimal("0")
        critical_description = "no critical-hit bonus"
    hit_multiplier = Decimal("1") + headshot_bonus + critical_bonus
    running *= hit_multiplier
    steps.append(
        DamageStep(
            4,
            "Hit-location and critical bucket",
            "1 + active HSD + active CHD contribution = "
            f"{_number(hit_multiplier)} ({critical_description})",
            hit_multiplier,
            running,
            applied=bool(headshot_bonus or critical_bonus),
        )
    )

    target_bonus = Decimal("0")
    target_terms: list[str] = []
    if inputs.target_has_armor:
        target_bonus += inputs.damage_to_armor + inputs.team_damage_to_armor
        target_terms.append("Damage to Armor")
    elif inputs.target_has_health:
        target_bonus += inputs.damage_to_health + inputs.team_damage_to_health
        target_terms.append("Damage to Health")
    target_multiplier = Decimal("1") + target_bonus
    running *= target_multiplier
    steps.append(
        DamageStep(
            5,
            "Target-layer damage",
            "1 + "
            + (" + ".join(target_terms) if target_terms else "no qualifying bonus")
            + f" = {_number(target_multiplier)}",
            target_multiplier,
            running,
            applied=bool(target_bonus),
        )
    )

    out_of_cover_bonus = (
        inputs.damage_to_targets_out_of_cover + inputs.team_damage_to_targets_out_of_cover
        if inputs.target_out_of_cover
        else Decimal("0")
    )
    out_of_cover_multiplier = Decimal("1") + out_of_cover_bonus
    running *= out_of_cover_multiplier
    steps.append(
        DamageStep(
            6,
            "Damage to Targets Out of Cover (DTOC/DTTOOC)",
            "1 + active DTOC = " + _number(out_of_cover_multiplier),
            out_of_cover_multiplier,
            running,
            applied=bool(out_of_cover_bonus),
        )
    )

    for amplifier in inputs.amplifiers:
        multiplier = Decimal("1") + amplifier.value
        running *= multiplier
        source = "team" if amplifier.team_buff else "personal"
        steps.append(
            DamageStep(
                len(steps) + 1,
                f"Amplified damage — {amplifier.name}",
                f"1 + {_percent(amplifier.value)} {source} amplifier = {_number(multiplier)}",
                multiplier,
                running,
                applied=bool(amplifier.value),
            )
        )

    notes = (
        "Multiplication is commutative; the ordered sequence explains bucket membership and "
        "activation, while the final product is unchanged by reordering multipliers.",
        "Headshot Damage and Critical Hit Damage share one additive hit bucket when the same "
        "projectile is both a headshot and a critical hit.",
        "Damage to Armor and Damage to Health are selected from the damage layer actually hit; "
        "DTOC applies separately only while the target is out of cover.",
        "A team buff is placed into Weapon Damage, Total Weapon Damage, HSD/CHD, target damage, "
        "or its own amplifier according to its current wording and verified behavior.",
    )
    return DamageBreakdown(
        inputs=inputs,
        steps=tuple(steps),
        final_damage=running,
        notes=notes,
    )


def render_damage_breakdown(breakdown: DamageBreakdown) -> str:
    lines = ["**Weapon damage calculation**", ""]
    for step in breakdown.steps:
        status = "applied" if step.applied else "inactive (\N{MULTIPLICATION SIGN}1.0000)"
        lines.extend(
            (
                f"{step.number}. **{step.name}** — {status}",
                f"   `{step.formula}`",
                f"   Running damage: `{_number(step.result)}`",
            )
        )
    lines.extend(("", f"**Final damage per projectile:** `{_number(breakdown.final_damage)}`"))
    lines.extend(("", "**Calculation notes**"))
    lines.extend(f"- {note}" for note in breakdown.notes)
    return "\n".join(lines)


_CALCULATION_INTENT = re.compile(
    r"\b(?:calculate|calculation|damage math|damage formula|show (?:me )?(?:the )?math|"
    r"break down (?:the )?damage|damage sequence)\b",
    re.IGNORECASE,
)
_NUMBER = r"([0-9][0-9,]*(?:\.[0-9]+)?)"


def parse_damage_question(text: str) -> DamageInputs | None:
    """Parse an explicitly labeled natural-language single-hit calculation request."""

    clean = " ".join(text.split())
    if not _CALCULATION_INTENT.search(clean):
        return None
    base_damage = _number_for(clean, (r"base(?: weapon)? damage", r"base"))
    if base_damage is None:
        return None

    team_weapon = _percent_for(clean, (r"team weapon damage",))
    team_total = _percent_for(clean, (r"team total weapon damage", r"team twd"))
    team_hsd = _percent_for(clean, (r"team headshot damage", r"team hsd"))
    team_chd = _percent_for(clean, (r"team critical hit damage", r"team crit damage", r"team chd"))
    team_dta = _percent_for(clean, (r"team damage to armor", r"team dta"))
    team_dth = _percent_for(clean, (r"team damage to health", r"team dth"))
    team_dtoc = _percent_for(
        clean,
        (
            r"team damage to targets? out of cover",
            r"team dttooc",
            r"team dtoc",
        ),
    )
    amplifiers = tuple(
        Amplifier(
            name=f"Amplifier {index}",
            value=Decimal(match.group(2)) / Decimal("100"),
            team_buff=bool(match.group(1)),
        )
        for index, match in enumerate(
            re.finditer(
                rf"\b(?:(team)\s+)?(?:amp(?:lifier)?(?:\s*\d+)?|amplified damage)"
                rf"\s*(?:is|=|:)?\s*{_NUMBER}\s*%",
                clean,
                re.IGNORECASE,
            ),
            start=1,
        )
    )
    lowered = clean.casefold()
    target_has_armor = bool(
        re.search(r"\b(?:armou?red target|target (?:has|with) armou?r|hitting armou?r)\b", lowered)
    )
    target_has_health = not target_has_armor or bool(
        re.search(r"\b(?:health target|target health|hitting health)\b", lowered)
    )
    target_out_of_cover = bool(
        re.search(
            r"\b(?:target|enemy) (?:is )?out of cover\b|\bout[- ]of[- ]cover target\b",
            lowered,
        )
    )
    headshot = bool(
        re.search(
            r"\b(?:shot|hit) (?:is |was )?(?:a )?headshot\b|\bheadshot (?:shot|hit|scenario)\b",
            lowered,
        )
    )
    critical_hit = bool(
        re.search(
            r"\b(?:shot|hit) (?:is |was )?(?:a )?(?:crit|critical hit)\b|"
            r"\b(?:confirmed|guaranteed) crit(?:ical hit)?\b|"
            r"\bcritical hit\b(?!\s+damage)",
            lowered,
        )
    )
    expected = bool(re.search(r"\b(?:average|expected) (?:hit |shot )?damage\b", lowered))
    return DamageInputs(
        base_damage=base_damage,
        weapon_damage=_personal_percent_for(
            clean,
            (r"all weapon damage", r"weapon damage", r"awd"),
            blocked_prefixes=("total ", "team ", "base ", "displayed "),
        ),
        weapon_type_damage=_percent_for(clean, (r"weapon type damage", r"wtd")),
        additive_weapon_damage=_percent_for(clean, (r"additive weapon damage",)),
        total_weapon_damage=_personal_percent_for(
            clean,
            (r"total weapon damage", r"twd"),
            blocked_prefixes=("team ",),
        ),
        headshot_damage=_personal_percent_for(
            clean,
            (r"headshot damage", r"hsd"),
            blocked_prefixes=("team ",),
        ),
        critical_hit_damage=_personal_percent_for(
            clean,
            (r"critical hit damage", r"crit damage", r"chd"),
            blocked_prefixes=("team ",),
        ),
        critical_hit_chance=_percent_for(clean, (r"critical hit chance", r"crit chance", r"chc")),
        damage_to_armor=_personal_percent_for(
            clean,
            (r"damage to armor", r"damage to armour", r"dta"),
            blocked_prefixes=("team ",),
        ),
        damage_to_health=_personal_percent_for(
            clean,
            (r"damage to health", r"dth"),
            blocked_prefixes=("team ",),
        ),
        damage_to_targets_out_of_cover=_personal_percent_for(
            clean,
            (
                r"damage to targets? out of cover",
                r"out of cover damage",
                r"dttooc",
                r"dtoc",
            ),
            blocked_prefixes=("team ",),
        ),
        team_weapon_damage=team_weapon,
        team_total_weapon_damage=team_total,
        team_headshot_damage=team_hsd,
        team_critical_hit_damage=team_chd,
        team_damage_to_armor=team_dta,
        team_damage_to_health=team_dth,
        team_damage_to_targets_out_of_cover=team_dtoc,
        amplifiers=amplifiers,
        headshot=headshot,
        critical_hit=critical_hit,
        expected_critical_value=expected,
        target_has_armor=target_has_armor,
        target_has_health=target_has_health,
        target_out_of_cover=target_out_of_cover,
        base_includes_weapon_damage_bucket=bool(
            re.search(r"\b(?:displayed|sheet) weapon damage\b", lowered)
        ),
    )


def _validate(inputs: DamageInputs) -> None:
    if inputs.base_damage <= 0:
        raise ValueError("base_damage must be greater than zero")
    if inputs.critical_hit and inputs.expected_critical_value:
        raise ValueError("choose a confirmed critical hit or expected critical value, not both")
    if not Decimal("0") <= inputs.critical_hit_chance <= Decimal("0.60"):
        raise ValueError("critical_hit_chance must be between 0 and the 60% cap")
    rates = (
        inputs.weapon_damage,
        inputs.weapon_type_damage,
        inputs.additive_weapon_damage,
        inputs.total_weapon_damage,
        inputs.headshot_damage,
        inputs.critical_hit_damage,
        inputs.damage_to_armor,
        inputs.damage_to_health,
        inputs.damage_to_targets_out_of_cover,
        inputs.team_weapon_damage,
        inputs.team_total_weapon_damage,
        inputs.team_headshot_damage,
        inputs.team_critical_hit_damage,
        inputs.team_damage_to_armor,
        inputs.team_damage_to_health,
        inputs.team_damage_to_targets_out_of_cover,
        *(amplifier.value for amplifier in inputs.amplifiers),
    )
    if any(rate < Decimal("-1") for rate in rates):
        raise ValueError("damage modifiers cannot be less than -100%")


def _number(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001')):,}"


def _percent(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.01'))}%"


def _number_for(text: str, labels: tuple[str, ...]) -> Decimal | None:
    for label in labels:
        if match := re.search(
            rf"\b(?:{label})\b\s*(?:is|=|:)?\s*{_NUMBER}",
            text,
            re.IGNORECASE,
        ):
            return Decimal(match.group(1).replace(",", ""))
    return None


def _percent_for(text: str, labels: tuple[str, ...]) -> Decimal:
    for label in labels:
        if match := re.search(
            rf"\b(?:{label})\b\s*(?:is|=|:)?\s*{_NUMBER}\s*%",
            text,
            re.IGNORECASE,
        ):
            return Decimal(match.group(1).replace(",", "")) / Decimal("100")
    return Decimal("0")


def _personal_percent_for(
    text: str,
    labels: tuple[str, ...],
    *,
    blocked_prefixes: tuple[str, ...],
) -> Decimal:
    for label in labels:
        for match in re.finditer(
            rf"\b(?:{label})\b\s*(?:is|=|:)?\s*{_NUMBER}\s*%",
            text,
            re.IGNORECASE,
        ):
            prefix = text[max(0, match.start() - 10) : match.start()].casefold()
            if not any(prefix.endswith(blocked) for blocked in blocked_prefixes):
                return Decimal(match.group(1).replace(",", "")) / Decimal("100")
    return Decimal("0")
