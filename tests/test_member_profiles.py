from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from rwi_bot.domain.schemas import AnswerTier
from rwi_bot.services.member_profiles import (
    infer_member_profile_update,
    is_profile_query,
    render_member_profile,
)
from rwi_bot.services.privacy import ProfileRepository


class FakeDatabase:
    def __init__(self, session: Any) -> None:
        self.fake_session = session

    @asynccontextmanager
    async def session(self) -> Any:
        yield self.fake_session


@pytest.mark.parametrize(
    "text",
    (
        "I'm SHD 5000 and Expertise 30.",
        "My SHD is 5000, expertise is 30.",
        "Update me to SHD 5000 and Expertise 30.",
        "Remember that I am SHD 5000, Expertise 30.",
    ),
)
def test_explicit_self_report_updates_numeric_profile(text: str) -> None:
    inferred = infer_member_profile_update(text)

    assert inferred is not None
    assert inferred.update.shd == 5000
    assert inferred.update.expertise == 30
    assert inferred.profile_only is True
    assert inferred.rejected == ()


def test_profile_update_can_precede_a_question() -> None:
    inferred = infer_member_profile_update(
        "I'm SHD 2500 and Expertise 20. What tank build should I use?"
    )

    assert inferred is not None
    assert inferred.update.shd == 2500
    assert inferred.update.expertise == 20
    assert inferred.profile_only is False


@pytest.mark.parametrize(
    "text",
    (
        "User A is SHD 2500 and Expertise 20.",
        "Is SHD 2500 enough?",
        "I'm looking for an Expertise 30 build.",
        "Make a level 40 build.",
    ),
)
def test_non_self_reports_do_not_change_profile(text: str) -> None:
    assert infer_member_profile_update(text) is None


def test_profile_preferences_are_recognized_only_as_explicit_defaults() -> None:
    mode = infer_member_profile_update("I play PvP.")
    detail = infer_member_profile_update("I prefer technical answers.")
    buffs = infer_member_profile_update("Include conditional buffs for my answers.")

    assert mode is not None and mode.update.mode == "PvP"
    assert detail is not None and detail.update.detail_tier is AnswerTier.TECHNICAL
    assert buffs is not None and buffs.update.include_conditional_buffs is True


def test_out_of_range_profile_value_is_rejected() -> None:
    inferred = infer_member_profile_update("Set my Expertise to 99.")

    assert inferred is not None
    assert inferred.update.expertise is None
    assert inferred.rejected == ("Expertise must be between 0 and 30.",)
    assert inferred.profile_only is True


@pytest.mark.parametrize(
    "text",
    ("Show my profile", "What's my ERIN profile?", "What do you remember about me?"),
)
def test_profile_queries_are_local(text: str) -> None:
    assert is_profile_query(text) is True


@pytest.mark.asyncio
async def test_profile_repository_persists_and_resolves_answer_assumptions() -> None:
    from unittest.mock import AsyncMock, Mock

    session = AsyncMock()
    session.add = Mock()
    session.get.return_value = None
    repository = ProfileRepository(FakeDatabase(session))  # type: ignore[arg-type]
    inferred = infer_member_profile_update(
        "I'm level 40, SHD 5000, Expertise 30. I play PvP. I prefer technical answers."
    )
    assert inferred is not None

    profile = await repository.update_answer_profile(42, inferred.update)

    stored = session.add.call_args.args[0]
    assert stored.discord_user_id == 42
    assert stored.shd_level == 5000
    assert stored.expertise_level == 30
    assert stored.preferences["mode"] == "PvP"
    assert profile.assumptions.shd == 5000
    assert profile.assumptions.expertise == 30
    assert profile.assumptions.mode == "PvP"
    assert profile.detail_tier is AnswerTier.TECHNICAL
    assert profile.persisted is True


@pytest.mark.asyncio
async def test_profile_repository_returns_safe_defaults_without_a_record() -> None:
    from unittest.mock import AsyncMock

    session = AsyncMock()
    session.get.return_value = None
    repository = ProfileRepository(FakeDatabase(session))  # type: ignore[arg-type]

    profile = await repository.get_answer_profile(42)

    assert profile.assumptions.shd == 1000
    assert profile.assumptions.expertise == 0
    assert profile.detail_tier is AnswerTier.STANDARD
    assert profile.persisted is False
    assert "Current defaults" in render_member_profile(profile)


@pytest.mark.asyncio
async def test_existing_profile_values_are_resolved_independently_per_user() -> None:
    from unittest.mock import AsyncMock

    session_a = AsyncMock()
    session_a.get.return_value = SimpleNamespace(
        shd_level=2500,
        expertise_level=20,
        detail_tier="standard",
        preferences={},
    )
    session_b = AsyncMock()
    session_b.get.return_value = SimpleNamespace(
        shd_level=10,
        expertise_level=0,
        detail_tier="concise",
        preferences={},
    )
    profile_a = await ProfileRepository(FakeDatabase(session_a)).get_answer_profile(1)  # type: ignore[arg-type]
    profile_b = await ProfileRepository(FakeDatabase(session_b)).get_answer_profile(2)  # type: ignore[arg-type]

    assert profile_a.assumptions.shd == 2500
    assert profile_b.assumptions.shd == 10
    assert profile_a.detail_tier is AnswerTier.STANDARD
    assert profile_b.detail_tier is AnswerTier.CONCISE
