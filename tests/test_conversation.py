from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from rwi_bot.cogs.conversation import (
    ConversationCog,
    ConversationTurn,
    is_profile_interview_request,
    member_cannot_supply_answer,
    profile_interview_update_text,
    split_discord_message,
)
from rwi_bot.db.models import CacheState
from rwi_bot.domain.schemas import AnswerAssumptions, AnswerResult, AnswerTier, SourceCitation
from rwi_bot.services.feedback import FeedbackSentiment, infer_feedback
from rwi_bot.services.member_profiles import MemberAnswerProfile


def test_discord_message_split_preserves_content() -> None:
    text = "alpha " * 800

    chunks = split_discord_message(text, limit=200)

    assert all(len(chunk) <= 200 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()


@pytest.mark.asyncio
async def test_normal_answer_has_no_sources_or_feedback_view() -> None:
    destination = SimpleNamespace(send=AsyncMock())
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    result = AnswerResult(
        text="Read the [guide](https://example.test/guide).",
        assumptions=AnswerAssumptions(
            level=40,
            shd=5000,
            expertise=30,
            mode="PvP",
            maximum_item_rolls=False,
            include_conditional_buffs=True,
        ),
        citations=[
            SourceCitation(
                title="Guide",
                url="https://example.test/guide",
                source_type="external_web",
            )
        ],
    )

    await cog._send_answer(cast(Any, destination), result)

    message = destination.send.call_args.args[0]
    assert "https://" not in message
    assert "**Sources**" not in message
    assert message == "Read the guide."
    assert "**Assumptions:**" not in message
    assert destination.send.call_args.kwargs == {}


def test_public_thread_context_keeps_member_authors_distinct() -> None:
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    cog._public_memory[99].append(
        ConversationTurn(
            member="I am SHD 2500.",
            assistant="Profile updated.",
            author_id=1,
            member_label="User A",
        )
    )
    cog._public_memory[99].append(
        ConversationTurn(
            member="What about me?",
            assistant="Using your own settings.",
            author_id=2,
            member_label="User B",
        )
    )

    summary = cog._conversation_summary((2, 99), destination_id=99, is_dm=False)

    assert summary is not None
    assert "Member User A: I am SHD 2500." in summary
    assert "ERIN answering User A" in summary
    assert "Member User B: What about me?" in summary


def test_private_dm_context_does_not_include_public_thread_memory() -> None:
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    cog._public_memory[99].append(
        ConversationTurn(member="public", assistant="public answer", member_label="Other")
    )
    cog._memory[(42, 99)].append(
        ConversationTurn(member="private", assistant="private answer", member_label="Self")
    )

    summary = cog._conversation_summary((42, 99), destination_id=99, is_dm=True)

    assert summary is not None
    assert "private answer" in summary
    assert "public answer" not in summary


def test_dm_personalization_interview_intent_matches_member_simulation_request() -> None:
    assert is_profile_interview_request(
        "I want you to take me through the personalization interview that you would send "
        "to brand new members. Pretend I am a new member."
    )
    assert is_profile_interview_request("Start my profile setup")
    assert not is_profile_interview_request("How do I get through the Dark Hours raid?")


def test_profile_interview_answers_are_labeled_for_the_existing_profile_parser() -> None:
    assert profile_interview_update_text(0, "PC and Xbox") == "Platform: PC and Xbox"
    assert profile_interview_update_text(1, "Mostly PvE, but some PvP") == "I play both"
    assert profile_interview_update_text(3, "AgentName") == "Gamertag: AgentName"
    assert profile_interview_update_text(3, "Ubisoft: AgentName") == "Ubisoft: AgentName"
    assert profile_interview_update_text(4, "Healer main") == "Playstyle: Healer main"
    assert profile_interview_update_text(5, "day-one player") == (
        "Add to my profile: day-one player"
    )


@pytest.mark.asyncio
async def test_profile_interview_saves_answer_and_advances_to_next_question() -> None:
    profile = MemberAnswerProfile(
        assumptions=AnswerAssumptions(platforms=["PC"]),
        detail_tier=AnswerTier.STANDARD,
        persisted=True,
    )
    profiles = SimpleNamespace(
        update_answer_profile=AsyncMock(return_value=profile),
        get_answer_profile=AsyncMock(return_value=profile),
    )
    audit = SimpleNamespace(record=AsyncMock())
    cog = ConversationCog(
        cast(
            Any,
            SimpleNamespace(
                services=SimpleNamespace(
                    profiles=profiles,
                    audit=audit,
                )
            ),
        )
    )
    cog._profile_interviews[42] = 0
    destination = SimpleNamespace(send=AsyncMock())
    message = SimpleNamespace(
        author=SimpleNamespace(id=42),
        content="PC",
        channel=SimpleNamespace(id=99),
    )

    await cog._handle_profile_interview_response(
        message=cast(Any, message),
        destination=cast(Any, destination),
        session_key=(42, 99),
        member_label="Agent",
    )

    update = profiles.update_answer_profile.call_args.args[1]
    assert update.platforms == ("PC",)
    assert cog._profile_interviews[42] == 1
    assert "Question 2 of 6" in destination.send.call_args.args[0]
    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_profile_interview_withholds_possible_personal_information() -> None:
    profile = MemberAnswerProfile(assumptions=AnswerAssumptions())
    profiles = SimpleNamespace(
        update_answer_profile=AsyncMock(return_value=profile),
        get_answer_profile=AsyncMock(return_value=profile),
    )
    cog = ConversationCog(
        cast(
            Any,
            SimpleNamespace(
                services=SimpleNamespace(
                    profiles=profiles,
                    audit=SimpleNamespace(record=AsyncMock()),
                )
            ),
        )
    )
    cog._profile_interviews[42] = 5
    destination = SimpleNamespace(send=AsyncMock())
    message = SimpleNamespace(
        author=SimpleNamespace(id=42),
        content="My birthday is January 1",
        channel=SimpleNamespace(id=99),
    )

    await cog._handle_profile_interview_response(
        message=cast(Any, message),
        destination=cast(Any, destination),
        session_key=(42, 99),
        member_label="Agent",
    )

    profiles.update_answer_profile.assert_not_awaited()
    assert cog._profile_interviews[42] == 5
    assert "possible personal information" in destination.send.call_args.args[0]
    assert cog._memory[(42, 99)][-1].member == "[possible personal information withheld]"


def test_any_public_participant_can_build_on_the_latest_erin_answer() -> None:
    cog = ConversationCog(cast(Any, SimpleNamespace()))
    answer = ConversationTurn(
        member="Give me a Heartbreaker build.",
        assistant="Use Gunner.",
        author_id=1,
        member_label="User A",
    )
    cog._public_memory[99].append(answer)

    assert cog._latest_public_answer(99) is answer


@pytest.mark.asyncio
async def test_archived_member_answer_stops_before_qa_creates_another_ticket() -> None:
    claim = SimpleNamespace(id=uuid4())
    learning = SimpleNamespace(submit_candidate=AsyncMock(return_value=claim))
    qa = SimpleNamespace(answer=AsyncMock())
    services = SimpleNamespace(
        settings=SimpleNamespace(discord_guild_id=1),
        qa=qa,
    )

    def get_cog(name: str) -> object | None:
        return learning if name == "CommunityLearningCog" else None

    bot = SimpleNamespace(services=services, get_cog=get_cog)
    cog = ConversationCog(cast(Any, bot))
    destination = SimpleNamespace(id=99, send=AsyncMock())
    cog._destination = AsyncMock(return_value=destination)  # type: ignore[method-assign]
    cog._is_ask_rwi_space = lambda _: True  # type: ignore[method-assign]
    prior = ConversationTurn(
        member="Can a Resolved shot trigger through an enemy shield?",
        assistant="I could not verify that. Do you know the answer?",
        author_id=42,
        member_label="Agent",
        question_signature="resolved-shield",
        awaiting_user_input=True,
    )
    cog._memory[(42, 99)].append(prior)
    cog._public_memory[99].append(prior)
    message = SimpleNamespace(
        author=SimpleNamespace(bot=False, id=42, display_name="Agent"),
        content=(
            "The answer is yes. Resolved triggers its headshot effect when the shot hits "
            "an enemy shield instead of the body."
        ),
        channel=SimpleNamespace(id=99),
        guild=SimpleNamespace(id=1),
    )

    await cog.on_message(cast(Any, message))

    learning.submit_candidate.assert_awaited_once()
    qa.answer.assert_not_awaited()
    assert prior.awaiting_user_input is False
    assert "archive for review" in destination.send.call_args.args[0]


@pytest.mark.asyncio
async def test_member_declining_to_answer_escalates_the_original_question_once() -> None:
    qa = SimpleNamespace(
        answer=AsyncMock(),
        escalate_unresolved=AsyncMock(return_value=uuid4()),
    )
    services = SimpleNamespace(
        settings=SimpleNamespace(discord_guild_id=1),
        profiles=SimpleNamespace(
            get_answer_profile=AsyncMock(
                return_value=MemberAnswerProfile(
                    assumptions=AnswerAssumptions(),
                    detail_tier=AnswerTier.STANDARD,
                )
            )
        ),
        qa=qa,
    )
    bot = SimpleNamespace(
        services=services,
        get_cog=lambda _: None,
        log=SimpleNamespace(info=Mock()),
    )
    cog = ConversationCog(cast(Any, bot))
    destination = SimpleNamespace(id=99, send=AsyncMock())
    cog._destination = AsyncMock(return_value=destination)  # type: ignore[method-assign]
    cog._is_ask_rwi_space = lambda _: True  # type: ignore[method-assign]
    prior = ConversationTurn(
        member="What is the current Iron Will shield interaction?",
        assistant="I could not verify that. Do you know the answer?",
        author_id=42,
        member_label="Agent",
        question_signature="iron-will-shield",
        awaiting_user_input=True,
        failure_code="insufficient_current_evidence",
        failure_summary="Current evidence did not establish the shield interaction.",
        used_web_search=True,
    )
    cog._memory[(42, 99)].append(prior)
    message = SimpleNamespace(
        author=SimpleNamespace(bot=False, id=42, display_name="Agent"),
        content="I don't know.",
        channel=SimpleNamespace(id=99),
        guild=SimpleNamespace(id=1),
    )

    await cog.on_message(cast(Any, message))

    qa.escalate_unresolved.assert_awaited_once()
    qa.answer.assert_not_awaited()
    assert prior.awaiting_user_input is False
    assert "plain-language summary" in destination.send.call_args.args[0]


@pytest.mark.asyncio
async def test_inferred_feedback_updates_cache_and_asks_for_correction() -> None:
    cache_id = uuid4()
    ticket_id = uuid4()
    services = SimpleNamespace(
        cache=SimpleNamespace(mark_feedback=AsyncMock(return_value=CacheState.CANDIDATE)),
        tickets=SimpleNamespace(open_or_increment=AsyncMock(return_value=ticket_id)),
        audit=SimpleNamespace(record=AsyncMock()),
    )
    cog = ConversationCog(cast(Any, SimpleNamespace(services=services)))
    turn = ConversationTurn(
        member="How do I get Nemesis?",
        assistant="Prior answer",
        cache_entry_id=cache_id,
        question_signature="question-signature",
    )
    inferred = infer_feedback("That's outdated.")

    outcome = await cog._apply_inferred_feedback(turn, inferred, user_id=42)

    assert outcome.recorded is True
    services.cache.mark_feedback.assert_awaited_once_with(cache_id, helpful=False)
    services.tickets.open_or_increment.assert_not_awaited()
    audit = services.audit.record.call_args.args[0]
    assert audit.event_type == "answer.feedback_inferred"
    assert audit.details["sentiment"] == "incorrect"
    assert turn.feedback_sentiment is FeedbackSentiment.INCORRECT
    assert turn.awaiting_user_input is True
    assert turn.failure_code == "member_reported_incorrect"


@pytest.mark.parametrize(
    "text",
    (
        "I don't know",
        "I don't know the correct answer.",
        "I'm not sure.",
        "No idea",
        "I can't answer that.",
        "Please ask the Technicians.",
    ),
)
def test_member_can_explicitly_defer_unresolved_question(text: str) -> None:
    assert member_cannot_supply_answer(text) is True


@pytest.mark.parametrize(
    "text",
    (
        "I don't know if that value is right, but I measured 25% in game.",
        "Can you ask the Technicians what Glass Cannon does?",
        "I am not sure why it works that way.",
    ),
)
def test_substantive_or_ambiguous_replies_do_not_trigger_automatic_escalation(text: str) -> None:
    assert member_cannot_supply_answer(text) is False


@pytest.mark.asyncio
async def test_repeated_inferred_feedback_is_deduplicated() -> None:
    services = SimpleNamespace(
        cache=SimpleNamespace(mark_feedback=AsyncMock(return_value=CacheState.ACTIVE)),
        tickets=SimpleNamespace(open_or_increment=AsyncMock()),
        audit=SimpleNamespace(record=AsyncMock()),
    )
    cog = ConversationCog(cast(Any, SimpleNamespace(services=services)))
    turn = ConversationTurn(
        member="Question",
        assistant="Answer",
        cache_entry_id=uuid4(),
        question_signature="signature",
        feedback_sentiment=FeedbackSentiment.HELPFUL,
    )

    outcome = await cog._apply_inferred_feedback(turn, infer_feedback("Thanks"), user_id=42)

    assert outcome.recorded is False
    services.cache.mark_feedback.assert_not_awaited()
    services.audit.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_exchange_is_not_eligible_for_answer_feedback() -> None:
    services = SimpleNamespace(
        cache=SimpleNamespace(mark_feedback=AsyncMock()),
        tickets=SimpleNamespace(open_or_increment=AsyncMock()),
        audit=SimpleNamespace(record=AsyncMock()),
    )
    cog = ConversationCog(cast(Any, SimpleNamespace(services=services)))
    turn = ConversationTurn(
        member="I'm SHD 5000 and Expertise 30.",
        assistant="Updated your ERIN profile.",
        answer_kind="profile",
        cache_entry_id=uuid4(),
        question_signature="must-not-be-scored",
    )

    outcome = await cog._apply_inferred_feedback(turn, infer_feedback("Thanks"), user_id=42)

    assert outcome.recorded is False
    assert outcome.eligible is False
    services.cache.mark_feedback.assert_not_awaited()
    services.tickets.open_or_increment.assert_not_awaited()
    services.audit.record.assert_not_awaited()
