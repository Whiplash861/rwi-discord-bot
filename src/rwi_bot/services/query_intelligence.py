from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from rwi_bot.domain.schemas import IntentKind, InterpretedQuestion
from rwi_bot.services.encounter_intent import EncounterPrediction
from rwi_bot.services.language import normalize_text
from rwi_bot.services.reference_catalog import ReferenceHit, is_specific_reference_hit


class _RetrievalHit(Protocol):
    entry: Any
    similarity: float


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """Deterministic routing context. It improves discovery but never supplies facts."""

    normalized_question: str
    primary_query: str
    retrieval_queries: tuple[str, ...]
    canonical_targets: tuple[str, ...]
    target_kind: str | None
    response_directives: tuple[str, ...]


def build_query_plan(
    *,
    interpreted: InterpretedQuestion,
    encounter: EncounterPrediction | None,
    reference_hits: Iterable[ReferenceHit],
) -> QueryPlan:
    primary_query = (
        encounter.search_query if encounter is not None else interpreted.normalized_question
    )
    queries = [primary_query, interpreted.normalized_question]
    targets: list[str] = []
    directives: list[str] = []
    target_kind: str | None = None

    if encounter is not None:
        target_kind = "encounter" if encounter.encounter else "activity"
        if encounter.encounter:
            targets.append(encounter.encounter)
            queries.extend(
                (encounter.encounter, f"{encounter.encounter} {encounter.activity or ''}")
            )
        if encounter.activity:
            targets.append(encounter.activity)
            queries.append(encounter.activity)
        directives.append(
            "Resolve the canonical activity and encounter before answering; preserve the "
            "member's requested scope and do not substitute a similarly named boss."
        )

    strong_reference_hits = [
        hit
        for hit in reference_hits
        if (
            (hit.match_kind == "exact" and hit.score >= 0.60)
            or (hit.match_kind == "fuzzy" and hit.score >= 0.75)
        )
        and is_specific_reference_hit(hit)
    ]
    exact_reference_hits = [hit for hit in strong_reference_hits if hit.match_kind == "exact"]
    if exact_reference_hits:
        strong_reference_hits = exact_reference_hits
    reference_names = list(dict.fromkeys(hit.record.name for hit in strong_reference_hits))[:4]
    queries.extend(reference_names)
    if strong_reference_hits and not targets:
        best_score = strong_reference_hits[0].score
        close_hits = [hit for hit in strong_reference_hits if best_score - hit.score <= 0.035]
        unique_names = list(dict.fromkeys(hit.record.name for hit in close_hits))
        if len(unique_names) == 1:
            target_kind = "reference_entity"
            targets.append(unique_names[0])
            queries.append(unique_names[0])
            directives.append(
                "Treat the resolved catalog name only as a spelling/search hint. Require "
                "current evidence for every factual claim about it."
            )

    normalized = interpreted.normalized_question
    if re_search_comparison(normalized):
        directives.append(
            "Compare every named option under the same assumptions. Separate rule/stat "
            "differences from practical tradeoffs and give a use-case verdict."
        )
    if interpreted.intent is IntentKind.ACQUISITION:
        directives.append(
            "Give the current legitimate acquisition route, prerequisites, lockouts or "
            "rotation limits, and a practical fallback when one is supported."
        )
    elif interpreted.intent in {IntentKind.BUILD_ADVICE, IntentKind.BUILD_RATING}:
        directives.append(
            "Check loadout legality and activation conditions before recommending the build. "
            "Explain the combat loop, substitutions, profile fit, and tiered pros and cons."
        )
    if any(term in normalized.split() for term in ("all", "every", "complete")):
        directives.append(
            "The member explicitly requested complete scope; cover every requested component "
            "or identify the exact component current evidence cannot establish."
        )

    if interpreted.constraints:
        rendered = ", ".join(
            f"{key}={value}" for key, value in sorted(interpreted.constraints.items())
        )
        directives.append(f"Apply these explicit member constraints: {rendered}.")

    return QueryPlan(
        normalized_question=interpreted.normalized_question,
        primary_query=primary_query,
        retrieval_queries=_unique_normalized(queries),
        canonical_targets=tuple(targets),
        target_kind=target_kind,
        response_directives=tuple(directives),
    )


def retrieval_supports_plan[HitT: _RetrievalHit](hits: list[HitT], plan: QueryPlan) -> bool:
    if not hits:
        return False
    if plan.canonical_targets:
        primary_target = normalize_text(plan.canonical_targets[0])
        target_terms = set(primary_target.split())
        for hit in hits:
            entry = hit.entry
            searchable = normalize_text(
                " ".join(
                    (
                        str(getattr(entry, "subject", "")),
                        str(getattr(entry, "search_text", "")),
                    )
                )
            )
            if primary_target in searchable or (
                target_terms and target_terms.issubset(set(searchable.split()))
            ):
                return True
        return False
    return max(float(getattr(hit, "similarity", 0.0)) for hit in hits) >= 0.24


def relevant_hits_for_plan[HitT: _RetrievalHit](hits: list[HitT], plan: QueryPlan) -> list[HitT]:
    """Keep canonical-target retrieval from being diluted by similarly worded records."""

    if not plan.canonical_targets:
        return hits
    target = normalize_text(plan.canonical_targets[0])
    target_terms = set(target.split())
    relevant: list[HitT] = []
    for hit in hits:
        entry = hit.entry
        searchable = normalize_text(
            " ".join(
                (
                    str(getattr(entry, "subject", "")),
                    str(getattr(entry, "search_text", "")),
                )
            )
        )
        if target in searchable or target_terms.issubset(set(searchable.split())):
            relevant.append(hit)
    return relevant


def prefer_latest_guide_hits[HitT: _RetrievalHit](hits: list[HitT]) -> list[HitT]:
    """Remove superseded encounter-guide rows while retaining complementary normal claims."""

    revisions_by_subject: dict[str, int] = {}
    for hit in hits:
        entry = hit.entry
        revision = _guide_revision(getattr(entry, "context", {}))
        if revision is not None:
            subject = normalize_text(str(getattr(entry, "subject", "")))
            revisions_by_subject[subject] = max(revisions_by_subject.get(subject, 0), revision)

    filtered: list[HitT] = []
    for hit in hits:
        entry = hit.entry
        subject = normalize_text(str(getattr(entry, "subject", "")))
        newest = revisions_by_subject.get(subject)
        if newest is None:
            filtered.append(hit)
            continue
        revision = _guide_revision(getattr(entry, "context", {}))
        if revision == newest:
            filtered.append(hit)
    return filtered


def query_plan_scope_prompt(plan: QueryPlan) -> str | None:
    if not plan.canonical_targets and not plan.response_directives:
        return None
    targets = ", ".join(plan.canonical_targets) or "none"
    directives = "\n".join(f"- {value}" for value in plan.response_directives)
    return (
        "QUERY INTELLIGENCE (routing context, not evidence):\n"
        f"- Canonical targets: {targets}\n"
        f"- Target type: {plan.target_kind or 'general'}\n"
        f"{directives}"
    )


def _unique_normalized(values: Iterable[str]) -> tuple[str, ...]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(" ".join(value.split()))
    return tuple(unique)


def _guide_revision(context: object) -> int | None:
    if not isinstance(context, dict) or "guide_revision" not in context:
        return None
    try:
        return int(context["guide_revision"])
    except (TypeError, ValueError):
        return None


def re_search_comparison(normalized: str) -> bool:
    tokens = set(normalized.split())
    return bool(tokens.intersection({"compare", "versus", "vs"})) or "better than" in normalized
