from __future__ import annotations

from types import SimpleNamespace

from rwi_bot.services.encounter_intent import predict_encounter_request
from rwi_bot.services.language import interpret_locally
from rwi_bot.services.query_intelligence import (
    build_query_plan,
    prefer_latest_guide_hits,
    relevant_hits_for_plan,
    retrieval_supports_plan,
)
from rwi_bot.services.reference_catalog import Division2ReferenceCatalog


def test_query_plan_adds_canonical_encounter_retrieval_variants() -> None:
    question = "How do I beet the luvbirds in merit estate?"
    interpreted = interpret_locally(question)
    encounter = predict_encounter_request(question)

    assert encounter is not None
    assert encounter.clarification is None
    plan = build_query_plan(
        interpreted=interpreted,
        encounter=encounter,
        reference_hits=[],
    )

    assert plan.canonical_targets[0] == "The Lovebirds: Martinez and Johnson"
    assert any("lovebirds" in query.casefold() for query in plan.retrieval_queries)
    assert any("paradise lost" in query.casefold() for query in plan.retrieval_queries)


def test_query_plan_uses_high_confidence_reference_name_as_search_hint() -> None:
    catalog = Division2ReferenceCatalog.packaged()
    interpreted = interpret_locally("What does Glas Canon do?")
    plan = build_query_plan(
        interpreted=interpreted,
        encounter=None,
        reference_hits=catalog.search("What does Glas Canon do?"),
    )

    assert plan.canonical_targets == ("Glass Cannon",)
    assert any(query.casefold() == "glass cannon" for query in plan.retrieval_queries)


def test_generic_reference_word_cannot_override_specific_stat_target() -> None:
    catalog = Division2ReferenceCatalog.packaged()
    question = "How do I get 6% armor regen?"
    plan = build_query_plan(
        interpreted=interpret_locally(question),
        encounter=None,
        reference_hits=catalog.search(question),
    )

    assert plan.canonical_targets == ("Armor Regeneration",)


def test_retrieval_must_contain_resolved_target() -> None:
    interpreted = interpret_locally("What does Glas Canon do?")
    catalog = Division2ReferenceCatalog.packaged()
    plan = build_query_plan(
        interpreted=interpreted,
        encounter=None,
        reference_hits=catalog.search("What does Glas Canon do?"),
    )
    unrelated = SimpleNamespace(
        entry=SimpleNamespace(subject="Vigilance", search_text="backpack talent"),
        similarity=0.91,
    )
    matching = SimpleNamespace(
        entry=SimpleNamespace(subject="Glass Cannon", search_text="chest talent"),
        similarity=0.51,
    )

    assert retrieval_supports_plan([unrelated], plan) is False
    assert retrieval_supports_plan([unrelated, matching], plan) is True
    assert relevant_hits_for_plan([unrelated, matching], plan) == [matching]


def test_comparison_plan_searches_each_exact_named_option() -> None:
    catalog = Division2ReferenceCatalog.packaged()
    question = "Compare Vigilance vs Composure"
    plan = build_query_plan(
        interpreted=interpret_locally(question),
        encounter=None,
        reference_hits=catalog.search(question),
    )

    queries = {query.casefold() for query in plan.retrieval_queries}
    assert "vigilance" in queries
    assert "composure" in queries
    assert plan.canonical_targets == ()
    assert any("same assumptions" in value for value in plan.response_directives)


def test_exact_reference_name_beats_a_higher_scoring_partial_fuzzy_name() -> None:
    catalog = Division2ReferenceCatalog.packaged()
    question = "Does bonus armor protect Vigilance?"
    plan = build_query_plan(
        interpreted=interpret_locally(question),
        encounter=None,
        reference_hits=catalog.search(question),
    )

    assert plan.canonical_targets == ("Vigilance",)


def test_latest_guide_revision_supersedes_older_same_subject() -> None:
    older = SimpleNamespace(
        entry=SimpleNamespace(subject="Wright", context={"guide_revision": 1}),
        similarity=0.9,
    )
    newer = SimpleNamespace(
        entry=SimpleNamespace(subject="Wright", context={"guide_revision": 2}),
        similarity=0.8,
    )
    complementary = SimpleNamespace(
        entry=SimpleNamespace(subject="Wright valve timing", context={}),
        similarity=0.7,
    )

    assert prefer_latest_guide_hits([older, newer, complementary]) == [newer, complementary]
