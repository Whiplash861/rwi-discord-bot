from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rwi_bot.db.models import KnowledgeStatus, SourceType
from rwi_bot.services.technician import (
    KnowledgeAction,
    parse_json_object,
    parse_source_evidence,
    propose_create,
    propose_revision,
    propose_rollback,
    render_create_proposal,
    render_proposal,
)


def entry_fixture() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        subject="Striker's Battlegear",
        content={"stacks": 100, "bonuses": {"damage": 0.65}},
        context={"mode": "pve"},
        status=KnowledgeStatus.ACTIVE.value,
        game_version="TU22",
        confidence=Decimal("0.900"),
        current_revision=3,
        revisions=[],
    )


def test_parse_json_object_rejects_invalid_or_non_object_json() -> None:
    assert parse_json_object('{"value": 1}', field_name="content") == {"value": 1}
    with pytest.raises(ValueError, match="valid JSON"):
        parse_json_object("{", field_name="content")
    with pytest.raises(ValueError, match="JSON object"):
        parse_json_object("[1, 2]", field_name="content")


def test_source_evidence_is_typed_and_rejects_secret_bearing_urls() -> None:
    sources = parse_source_evidence(
        """[
          {
            "url": "https://www.ubisoft.com/example",
            "title": "Official patch notes",
            "source_type": "official",
            "trust_score": 0.95,
            "publisher": "Ubisoft"
          }
        ]"""
    )

    assert len(sources) == 1
    assert sources[0].source_type is SourceType.OFFICIAL
    assert sources[0].trust_score == Decimal("0.950")
    assert sources[0].supports_claim is True

    with pytest.raises(ValueError, match="credential or secret"):
        parse_source_evidence(
            """[
              {
                "url": "https://example.test/report?token=do-not-store",
                "title": "Unsafe link",
                "source_type": "unverified",
                "trust_score": 0.2
              }
            ]"""
        )


def test_create_proposal_requires_supporting_evidence_for_active_truth() -> None:
    opposing = parse_source_evidence(
        """[
          {
            "url": "https://example.test/counterexample",
            "title": "Counterexample",
            "source_type": "reproducible_test",
            "trust_score": 0.8,
            "supports_claim": false
          }
        ]"""
    )

    with pytest.raises(ValueError, match="supporting source"):
        propose_create(
            subject="Example item",
            entity_type="gear",
            claim_key="stats",
            content={"armor": 100_000},
            context={"mode": "pve"},
            status=KnowledgeStatus.ACTIVE,
            game_version="TU23",
            confidence=0.8,
            sources=opposing,
            reason="Document a test result",
        )


def test_create_proposal_normalizes_identity_and_renders_source_snapshot() -> None:
    sources = parse_source_evidence(
        """[
          {
            "url": "https://example.test/repro",
            "title": "Reproducible test",
            "source_type": "reproducible_test",
            "trust_score": 0.875,
            "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
          }
        ]"""
    )

    proposal = propose_create(
        subject="  Example   Item ",
        entity_type=" Gear_Set ",
        claim_key=" PvE.Stats ",
        content={"hazard_protection": 0.1},
        context={"mode": "pve"},
        status=KnowledgeStatus.ACTIVE,
        game_version=" TU23 ",
        confidence=0.9,
        sources=sources,
        reason="  Verified in a controlled test  ",
    )

    assert proposal.subject == "Example Item"
    assert proposal.entity_type == "gear_set"
    assert proposal.claim_key == "pve.stats"
    assert proposal.game_version == "TU23"
    assert proposal.reason == "Verified in a controlled test"
    rendered = render_create_proposal(proposal)
    assert "immutable source snapshot" in rendered
    assert "reproducible_test" in rendered


def test_revision_proposal_is_typed_and_contains_nested_diff() -> None:
    entry = entry_fixture()

    proposal = propose_revision(
        entry,  # type: ignore[arg-type]
        content={"stacks": 100, "bonuses": {"damage": 0.7}, "source": "test"},
        context=None,
        status=None,
        game_version="TU23",
        clear_game_version=False,
        confidence=0.95,
        reason="  Reproduced after the title update  ",
    )

    assert proposal.action == KnowledgeAction.REVISE
    assert proposal.expected_current_revision == 3
    assert proposal.next_revision_number == 4
    assert proposal.reason == "Reproduced after the title update"
    assert proposal.confidence == Decimal("0.950")
    assert {change.path for change in proposal.changes} == {
        "$.confidence",
        "$.content.bonuses.damage",
        "$.content.source",
        "$.game_version",
    }


def test_revision_proposal_rejects_noop() -> None:
    entry = entry_fixture()

    with pytest.raises(ValueError, match="does not change"):
        propose_revision(
            entry,  # type: ignore[arg-type]
            content=entry.content,
            context=None,
            status=None,
            game_version=None,
            clear_game_version=False,
            confidence=None,
            reason="No actual change",
        )


def test_rollback_proposal_restores_historical_snapshot_as_new_revision() -> None:
    entry = entry_fixture()
    target = SimpleNamespace(
        revision_number=1,
        content={"stacks": 50},
        context={"mode": "pve"},
        status=KnowledgeStatus.SUPERSEDED.value,
        game_version="TU20",
        confidence=Decimal("0.750"),
    )
    entry.revisions = [target]

    proposal = propose_rollback(
        entry,  # type: ignore[arg-type]
        target_revision_number=1,
        reason="Restore known-good values",
    )

    assert proposal.action == KnowledgeAction.ROLLBACK
    assert proposal.target_revision_number == 1
    assert proposal.next_revision_number == 4
    assert proposal.content == {"stacks": 50}
    assert proposal.status == KnowledgeStatus.SUPERSEDED
    assert "rollback" in render_proposal(proposal).lower()


def test_render_proposal_obeys_discord_message_budget() -> None:
    entry = entry_fixture()
    proposal = propose_revision(
        entry,  # type: ignore[arg-type]
        content={f"field-{index}": "x" * 200 for index in range(30)},
        context=None,
        status=None,
        game_version=None,
        clear_game_version=False,
        confidence=None,
        reason="Bulk verified replacement",
    )

    rendered = render_proposal(proposal, max_chars=600)

    assert len(rendered) <= 600
    assert "more changed field" in rendered


def test_revision_proposal_can_explicitly_clear_game_version() -> None:
    entry = entry_fixture()

    proposal = propose_revision(
        entry,  # type: ignore[arg-type]
        content={**entry.content, "note": "version independent"},
        context=None,
        status=None,
        game_version=None,
        clear_game_version=True,
        confidence=None,
        reason="Verified as version independent",
    )

    assert proposal.game_version is None
    with pytest.raises(ValueError, match="not both"):
        propose_revision(
            entry,  # type: ignore[arg-type]
            content={"value": 1},
            context=None,
            status=None,
            game_version="TU23",
            clear_game_version=True,
            confidence=None,
            reason="Conflicting input",
        )
