from __future__ import annotations

from rwi_bot.services.knowledge_syllabus import (
    CURRENT_Y8S3_PRIMARY_REFERENCES,
    KNOWLEDGE_SYLLABUS,
    identify_knowledge_domains,
    knowledge_scope_prompt,
)


def test_syllabus_covers_every_requested_knowledge_domain() -> None:
    keys = {domain.key for domain in KNOWLEDGE_SYLLABUS}

    assert len(KNOWLEDGE_SYLLABUS) == 21
    assert len(keys) == len(KNOWLEDGE_SYLLABUS)
    assert {
        "exotic_gear",
        "exotic_weapons",
        "named_items",
        "standard_arsenal",
        "talents",
        "rarity",
        "difficulty",
        "directives",
        "mission_types",
        "skills",
        "progression_costs",
        "special_missions",
        "lore",
        "enemy_factions",
        "incursion_bosses",
        "buildcraft",
        "combat_math",
        "raids",
        "dark_zone",
        "progression",
        "live_service",
    } == keys
    assert all(len(domain.required_facets) >= 5 for domain in KNOWLEDGE_SYLLABUS)
    assert all(url.startswith("https://") for url in CURRENT_Y8S3_PRIMARY_REFERENCES)


def test_syllabus_routes_specific_member_questions() -> None:
    assert [
        domain.key
        for domain in identify_knowledge_domains(
            "Where does this Exotic weapon drop and what is its talent?"
        )
    ] == ["exotic_weapons", "talents"]
    assert [
        domain.key for domain in identify_knowledge_domains("What does Fog of War change?")
    ] == ["directives"]
    assert [domain.key for domain in identify_knowledge_domains("Explain Wright's mechanics")] == [
        "incursion_bosses"
    ]
    assert [
        domain.key
        for domain in identify_knowledge_domains("Show DTOC damage math for my healer build")
    ] == ["buildcraft", "combat_math"]


def test_syllabus_prompt_marks_reference_pages_as_discovery_not_evidence() -> None:
    prompt = knowledge_scope_prompt("Show every Skill Tier bonus for the Shield")

    assert prompt is not None
    assert "Skills and Skill Tiers" in prompt
    assert "Skill Tier 1-6 scaling" in prompt
    assert "not evidence by themselves" in prompt
