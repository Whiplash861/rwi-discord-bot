from __future__ import annotations

import asyncio
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from uuid import UUID

import discord
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.domain.schemas import (
    AnswerRequest,
    AnswerResult,
    AuditRecord,
    SourceCitation,
)
from rwi_bot.services.community_learning import infer_community_claim
from rwi_bot.services.feedback import FeedbackSentiment, InferredFeedback, infer_feedback
from rwi_bot.services.knowledge import sanitize_for_technicians
from rwi_bot.services.language import interpret_locally, question_signature
from rwi_bot.services.member_profiles import (
    InferredMemberProfileUpdate,
    MemberAnswerProfile,
    infer_member_profile_update,
    is_profile_query,
    render_member_profile,
)
from rwi_bot.services.rate_limit import MemberRateLimiter
from rwi_bot.services.sources import hide_source_links, is_source_request, render_sources


@dataclass(slots=True)
class ConversationTurn:
    member: str
    assistant: str
    author_id: int | None = None
    member_label: str | None = None
    answer_kind: str = "answer"
    citations: tuple[SourceCitation, ...] = ()
    cache_entry_id: UUID | None = None
    learning_opt_out: bool = False
    question_signature: str | None = None
    is_dm: bool = False
    feedback_sentiment: FeedbackSentiment | None = None


@dataclass(frozen=True, slots=True)
class FeedbackOutcome:
    recorded: bool
    ticket_id: UUID | None = None
    eligible: bool = False


class ConversationCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.rate_limiter = MemberRateLimiter()
        self._locks: defaultdict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)
        self._memory: defaultdict[tuple[int, int], deque[ConversationTurn]] = defaultdict(
            lambda: deque(maxlen=4)
        )
        self._public_memory: defaultdict[int, deque[ConversationTurn]] = defaultdict(
            lambda: deque(maxlen=6)
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content.strip():
            return
        is_dm = isinstance(message.channel, discord.DMChannel)
        if is_dm:
            member = await self._live_member(message.author.id)
            if member is None:
                await message.channel.send(
                    "ERIN direct-message access is available only while you are a current "
                    "member of The Redwing Initiative server."
                )
                return
        else:
            if (
                message.guild is None
                or message.guild.id != self.bot.services.settings.discord_guild_id
            ):
                return
            if not self._is_ask_rwi_space(message.channel):
                return

            moderation = self.bot.get_cog("ModerationCog")
            if moderation is not None and await moderation.handle_message(message):  # type: ignore[attr-defined]
                return

        destination = await self._destination(message)
        session_key = (message.author.id, destination.id)
        member_label = self._member_label(message.author.display_name)
        async with self._locks[session_key]:
            prior_turn = self._memory[session_key][-1] if self._memory[session_key] else None
            inferred = infer_feedback(message.content)
            outcome = await self._apply_inferred_feedback(
                prior_turn,
                inferred,
                user_id=message.author.id,
            )

            if is_source_request(message.content):
                if prior_turn is None:
                    await destination.send(
                        "I don't have a previous answer in this conversation to source yet."
                    )
                elif prior_turn.answer_kind == "profile":
                    await destination.send(
                        "That was a local profile response based on settings you supplied; "
                        "it didn't use an external source."
                    )
                else:
                    for chunk in split_discord_message(render_sources(prior_turn.citations)):
                        await destination.send(chunk)
                return

            if inferred is not None and inferred.feedback_only:
                await destination.send(self._feedback_reply(inferred, prior_turn, outcome))
                return

            profile: MemberAnswerProfile | None = None
            profile_update = infer_member_profile_update(message.content)
            if profile_update is not None:
                if profile_update.update.fields:
                    profile = await self.bot.services.profiles.update_answer_profile(
                        message.author.id,
                        profile_update.update,
                    )
                    await self.bot.services.audit.record(
                        AuditRecord(
                            event_type="profile.answer_preferences_updated",
                            actor_id=message.author.id,
                            target_type="user_profile",
                            target_id="self",
                            reason="Explicit member self-report",
                            details={
                                "fields": list(profile_update.update.fields),
                                "is_dm": is_dm,
                            },
                        )
                    )
                else:
                    profile = await self.bot.services.profiles.get_answer_profile(message.author.id)
                profile_reply = self._profile_update_reply(profile, profile_update)
                if profile_update.profile_only:
                    await destination.send(profile_reply)
                    self._remember_local_exchange(
                        session_key=session_key,
                        destination_id=destination.id,
                        is_dm=is_dm,
                        author_id=message.author.id,
                        member_label=member_label,
                        member_text=message.content,
                        assistant_text=profile_reply,
                    )
                    return
                await destination.send(profile_reply)

            if is_profile_query(message.content):
                profile = profile or await self.bot.services.profiles.get_answer_profile(
                    message.author.id
                )
                profile_reply = render_member_profile(profile)
                await destination.send(profile_reply)
                self._remember_local_exchange(
                    session_key=session_key,
                    destination_id=destination.id,
                    is_dm=is_dm,
                    author_id=message.author.id,
                    member_label=member_label,
                    member_text=message.content,
                    assistant_text=profile_reply,
                )
                return

            retry_after = await self.rate_limiter.acquire(message.author.id)
            if retry_after is not None:
                seconds = max(int(retry_after.total_seconds()), 1)
                await message.reply(
                    f"You've reached the fair-use limit. Try again in about {seconds} seconds."
                )
                return

            learning_turn = self._latest_public_answer(destination.id) if not is_dm else None
            if learning_turn is not None:
                claim_proposal = infer_community_claim(message.content)
                learning = self.bot.get_cog("CommunityLearningCog")
                if claim_proposal is not None and learning is not None:
                    claim = await learning.submit_candidate(  # type: ignore[attr-defined]
                        message,
                        proposal=claim_proposal,
                        member_label=member_label,
                        source_question=learning_turn.member,
                        prior_answer_excerpt=learning_turn.assistant,
                    )
                    if claim is not None:
                        await destination.send(
                            "Thanks—that is substantial enough to archive for review. I asked "
                            "experienced members to verify it. I won't reuse it as fact unless "
                            "they approve or qualify it, and bug or exploit techniques are "
                            "excluded from recommendations."
                        )

            profile = profile or await self.bot.services.profiles.get_answer_profile(
                message.author.id
            )
            summary = self._conversation_summary(
                session_key,
                destination_id=destination.id,
                is_dm=is_dm,
            )
            request = AnswerRequest(
                user_id=message.author.id,
                guild_id=self.bot.services.settings.discord_guild_id,
                channel_id=message.channel.id,
                member_name=member_label,
                question=message.content,
                tier=profile.detail_tier,
                assumptions=profile.assumptions,
                conversation_summary=summary,
                is_dm=is_dm,
            )
            async with destination.typing():
                result = await self.bot.services.qa.answer(request)
            await self._send_answer(destination, result)
            signature = self._question_signature(request)
            turn = ConversationTurn(
                member=message.content[:1200],
                assistant=hide_source_links(result.text, tuple(result.citations))[:1800],
                author_id=message.author.id,
                member_label=member_label,
                citations=tuple(result.citations),
                cache_entry_id=result.cache_entry_id,
                learning_opt_out=result.learning_opt_out,
                question_signature=signature,
                is_dm=is_dm,
            )
            self._memory[session_key].append(turn)
            if not is_dm:
                self._public_memory[destination.id].append(turn)

    async def _live_member(self, user_id: int) -> discord.Member | None:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None:
            return None
        try:
            return await guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    @staticmethod
    def _is_ask_rwi_space(channel: discord.abc.Messageable) -> bool:
        if isinstance(channel, discord.TextChannel):
            return channel.name == names.ASK_RWI
        if isinstance(channel, discord.Thread):
            return channel.parent is not None and channel.parent.name == names.ASK_RWI
        return False

    async def _destination(
        self, message: discord.Message
    ) -> discord.DMChannel | discord.TextChannel | discord.Thread:
        if isinstance(message.channel, (discord.DMChannel, discord.Thread)):
            return message.channel
        if not isinstance(message.channel, discord.TextChannel):
            raise TypeError("RWI conversation destination must be a text channel or thread.")
        title = f"{message.author.display_name}: {message.content.strip()}"
        title = " ".join(title.split())[:90]
        try:
            return await message.create_thread(
                name=title,
                auto_archive_duration=1440,
                reason="Keep RWI question context separated",
            )
        except (discord.Forbidden, discord.HTTPException):
            return message.channel

    def _conversation_summary(
        self,
        session_key: tuple[int, int],
        *,
        destination_id: int | None = None,
        is_dm: bool = True,
    ) -> str | None:
        turns = (
            self._memory[session_key]
            if is_dm or destination_id is None
            else self._public_memory[destination_id]
        )
        if not turns:
            return None
        parts: list[str] = []
        for turn in turns:
            label = turn.member_label or "Member"
            parts.append(f"Member {label}: {turn.member}\nERIN answering {label}: {turn.assistant}")
        return "\n\n".join(parts)[:6000]

    def clear_user_memory(self, user_id: int) -> int:
        keys = [key for key in self._memory if key[0] == user_id]
        for key in keys:
            del self._memory[key]
        for destination_id, turns in list(self._public_memory.items()):
            retained = [turn for turn in turns if turn.author_id != user_id]
            if retained:
                self._public_memory[destination_id] = deque(retained, maxlen=6)
            else:
                del self._public_memory[destination_id]
        return len(keys)

    def _latest_public_answer(self, destination_id: int) -> ConversationTurn | None:
        return next(
            (
                turn
                for turn in reversed(self._public_memory[destination_id])
                if turn.answer_kind == "answer"
            ),
            None,
        )

    def _remember_local_exchange(
        self,
        *,
        session_key: tuple[int, int],
        destination_id: int,
        is_dm: bool,
        author_id: int,
        member_label: str,
        member_text: str,
        assistant_text: str,
    ) -> None:
        turn = ConversationTurn(
            member=member_text[:1200],
            assistant=assistant_text[:1800],
            author_id=author_id,
            member_label=member_label,
            answer_kind="profile",
        )
        self._memory[session_key].append(turn)
        if not is_dm:
            self._public_memory[destination_id].append(turn)

    @staticmethod
    def _member_label(display_name: str) -> str:
        clean = re.sub(r"[\r\n\t]+", " ", display_name)
        clean = " ".join(clean.split())[:80]
        return clean or "Member"

    @staticmethod
    def _profile_update_reply(
        profile: MemberAnswerProfile,
        inference: InferredMemberProfileUpdate,
    ) -> str:
        if inference.update.fields:
            response = render_member_profile(profile, updated=True)
        else:
            response = "I couldn't update your ERIN profile."
        if inference.rejected:
            response += "\n\nSkipped:\n" + "\n".join(f"- {reason}" for reason in inference.rejected)
        return response

    async def _apply_inferred_feedback(
        self,
        turn: ConversationTurn | None,
        inferred: InferredFeedback | None,
        *,
        user_id: int,
    ) -> FeedbackOutcome:
        if turn is None or inferred is None:
            return FeedbackOutcome(recorded=False, eligible=False)
        if turn.answer_kind != "answer":
            return FeedbackOutcome(recorded=False, eligible=False)
        if turn.feedback_sentiment is inferred.sentiment:
            return FeedbackOutcome(recorded=False, eligible=True)
        if turn.feedback_sentiment is FeedbackSentiment.INCORRECT:
            return FeedbackOutcome(recorded=False, eligible=True)

        cache_state: str | None = None
        ticket_id: UUID | None = None
        if turn.cache_entry_id is not None and not turn.learning_opt_out:
            try:
                state = await self.bot.services.cache.mark_feedback(
                    turn.cache_entry_id,
                    helpful=inferred.sentiment is FeedbackSentiment.HELPFUL,
                )
            except KeyError:
                cache_state = "missing"
            else:
                cache_state = state.value

        if (
            inferred.sentiment is FeedbackSentiment.INCORRECT
            and turn.question_signature is not None
        ):
            ticket_id = await self.bot.services.tickets.open_or_increment(
                signature=turn.question_signature,
                sanitized_question=sanitize_for_technicians(turn.member),
                requester_user_id=None if turn.learning_opt_out else user_id,
            )

        if not turn.learning_opt_out:
            await self.bot.services.audit.record(
                AuditRecord(
                    event_type="answer.feedback_inferred",
                    actor_id=user_id,
                    target_type=("answer_cache" if turn.cache_entry_id is not None else "answer"),
                    target_id=(
                        str(turn.cache_entry_id)
                        if turn.cache_entry_id is not None
                        else turn.question_signature
                    ),
                    reason=(
                        "Member explicitly indicated the prior answer was incorrect or outdated"
                        if inferred.sentiment is FeedbackSentiment.INCORRECT
                        else None
                    ),
                    details={
                        "sentiment": inferred.sentiment.value,
                        "method": "explicit_follow_up",
                        "cache_state": cache_state,
                        "ticket_id": str(ticket_id) if ticket_id is not None else None,
                        "is_dm": turn.is_dm,
                    },
                )
            )
        turn.feedback_sentiment = inferred.sentiment
        return FeedbackOutcome(recorded=True, ticket_id=ticket_id, eligible=True)

    @staticmethod
    def _feedback_reply(
        inferred: InferredFeedback,
        turn: ConversationTurn | None,
        outcome: FeedbackOutcome,
    ) -> str:
        if inferred.sentiment is FeedbackSentiment.HELPFUL:
            return "Glad that helped."
        if turn is None or not outcome.eligible:
            return "Tell me which answer was wrong or outdated, and I'll take another look."
        if not outcome.recorded:
            return "I already recorded that concern."
        if outcome.ticket_id is not None:
            return (
                "Thanks for flagging it. I recorded the answer for review under ticket "
                f"`{outcome.ticket_id}`."
            )
        return "Thanks for flagging it. I recorded that the answer needs another look."

    def _question_signature(self, request: AnswerRequest) -> str:
        interpreted = interpret_locally(request.question)
        return question_signature(
            interpreted.normalized_question,
            assumptions=request.assumptions.model_dump(mode="json"),
            constraints={
                **interpreted.constraints,
                "current_game_version": self.bot.services.settings.current_game_version,
            },
        )

    async def _send_answer(
        self,
        destination: discord.abc.Messageable,
        result: AnswerResult,
    ) -> None:
        body = hide_source_links(result.text, tuple(result.citations))
        chunks = split_discord_message(body)
        for chunk in chunks:
            await destination.send(chunk)


def split_discord_message(text: str, *, limit: int = 1950) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks
