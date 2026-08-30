from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rwi_bot.db.models import KnowledgeStatus
from rwi_bot.services.technician import (
    KnowledgeAction,
    parse_json_object,
    propose_revision,
    propose_rollback,
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
