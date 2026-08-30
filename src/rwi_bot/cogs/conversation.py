from __future__ import annotations

import asyncio
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
    AnswerTier,
    AuditRecord,
    SourceCitation,
)
from rwi_bot.services.feedback import FeedbackSentiment, InferredFeedback, infer_feedback
from rwi_bot.services.knowledge import sanitize_for_technicians
from rwi_bot.services.language import interpret_locally, question_signature
from rwi_bot.services.rate_limit import MemberRateLimiter
from rwi_bot.services.sources import hide_source_links, is_source_request, render_sources


@dataclass(slots=True)
class ConversationTurn:
    member: str
    assistant: str
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


class ConversationCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.rate_limiter = MemberRateLimiter()
        self._locks: defaultdict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)
        self._memory: defaultdict[tuple[int, int], deque[ConversationTurn]] = defaultdict(
            lambda: deque(maxlen=4)
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
                else:
                    for chunk in split_discord_message(render_sources(prior_turn.citations)):
                        await destination.send(chunk)
                return

            if inferred is not None and inferred.feedback_only:
                await destination.send(self._feedback_reply(inferred, prior_turn, outcome))
                return

            retry_after = await self.rate_limiter.acquire(message.author.id)
            if retry_after is not None:
                seconds = max(int(retry_after.total_seconds()), 1)
                await message.reply(
                    f"You've reached the fair-use limit. Try again in about {seconds} seconds."
                )
                return

            summary = self._conversation_summary(session_key)
            request = AnswerRequest(
                user_id=message.author.id,
                guild_id=self.bot.services.settings.discord_guild_id,
                channel_id=message.channel.id,
                question=message.content,
                tier=AnswerTier.STANDARD,
                conversation_summary=summary,
                is_dm=is_dm,
            )
            async with destination.typing():
                result = await self.bot.services.qa.answer(request)
            await self._send_answer(destination, result)
            signature = self._question_signature(request)
            self._memory[session_key].append(
                ConversationTurn(
                    member=message.content[:1200],
                    assistant=hide_source_links(result.text, tuple(result.citations))[:1800],
                    citations=tuple(result.citations),
                    cache_entry_id=result.cache_entry_id,
                    learning_opt_out=result.learning_opt_out,
                    question_signature=signature,
                    is_dm=is_dm,
                )
            )

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

    def _conversation_summary(self, session_key: tuple[int, int]) -> str | None:
        turns = self._memory[session_key]
        if not turns:
            return None
        parts: list[str] = []
        for turn in turns:
            parts.append(f"Member: {turn.member}\nERIN: {turn.assistant}")
        return "\n\n".join(parts)[:6000]

    def clear_user_memory(self, user_id: int) -> int:
        keys = [key for key in self._memory if key[0] == user_id]
        for key in keys:
            del self._memory[key]
        return len(keys)

    async def _apply_inferred_feedback(
        self,
        turn: ConversationTurn | None,
        inferred: InferredFeedback | None,
        *,
        user_id: int,
    ) -> FeedbackOutcome:
        if turn is None or inferred is None:
            return FeedbackOutcome(recorded=False)
        if turn.feedback_sentiment is inferred.sentiment:
            return FeedbackOutcome(recorded=False)
        if turn.feedback_sentiment is FeedbackSentiment.INCORRECT:
            return FeedbackOutcome(recorded=False)

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
        return FeedbackOutcome(recorded=True, ticket_id=ticket_id)

    @staticmethod
    def _feedback_reply(
        inferred: InferredFeedback,
        turn: ConversationTurn | None,
        outcome: FeedbackOutcome,
    ) -> str:
        if inferred.sentiment is FeedbackSentiment.HELPFUL:
            return "Glad that helped."
        if turn is None:
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
        body += (
            "\n\n**Assumptions:** Level 40 · SHD "
            f"{result.assumptions.shd} · Expertise {result.assumptions.expertise} · "
            f"{result.assumptions.mode} · maximum rolls"
        )
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
