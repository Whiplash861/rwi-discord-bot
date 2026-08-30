from __future__ import annotations

from rwi_bot.services.reference_catalog import (
    Division2ReferenceCatalog,
    reference_scope_prompt,
)


def test_packaged_reference_snapshot_is_pinned_and_complete() -> None:
    catalog = Division2ReferenceCatalog.packaged()

    assert catalog.snapshot.commit == "87b6dcbbceeb3937255b1987b53f91573f549825"
    assert catalog.snapshot.license == "CC-BY-4.0"
    assert catalog.snapshot.record_count == 2037
    assert len(catalog.records) == 2037


def test_reference_catalog_finds_current_named_items_and_talents() -> None:
    catalog = Division2ReferenceCatalog.packaged()

    iron_will = catalog.search("What does the Iron Will exotic chest do?")
    glass_cannon = catalog.search("What is the Glass Cannon chest talent?")
    boiling_point = catalog.search("Which weapons have Perfect Boiling Point?")

    assert iron_will[0].record.name == "Iron Will"
    assert any(hit.record.name == "Glass Cannon" for hit in glass_cannon)
    assert any(hit.record.name == "Perfect Boiling Point" for hit in boiling_point)


def test_reference_scope_is_explicitly_non_evidentiary_and_attributed() -> None:
    catalog = Division2ReferenceCatalog.packaged()
    hits = catalog.search("Fafnir exotic shotgun")

    scope = reference_scope_prompt(hits, catalog.snapshot)

    assert scope is not None
    assert "discovery hints only, not verified evidence" in scope
    assert "div2hub/game-data" in scope
    assert "87b6dcbbceeb" in scope
    assert "Fafnir" in scope


def test_reference_catalog_ignores_empty_or_nonsemantic_queries() -> None:
    catalog = Division2ReferenceCatalog.packaged()

    assert catalog.search("what is it") == []
