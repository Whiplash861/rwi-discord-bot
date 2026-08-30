from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass

import discord
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.views import FeedbackView
from rwi_bot.domain.schemas import AnswerRequest, AnswerResult, AnswerTier, AuditRecord
from rwi_bot.services.knowledge import sanitize_for_technicians
from rwi_bot.services.language import interpret_locally, question_signature
from rwi_bot.services.rate_limit import MemberRateLimiter


@dataclass(slots=True)
class ConversationTurn:
    member: str
    assistant: str


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

        retry_after = await self.rate_limiter.acquire(message.author.id)
        if retry_after is not None:
            seconds = max(int(retry_after.total_seconds()), 1)
            await message.reply(
                f"You've reached the fair-use limit. Try again in about {seconds} seconds."
            )
            return

        destination = await self._destination(message)
        session_key = (message.author.id, destination.id)
        async with self._locks[session_key]:
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
            await self._send_answer(destination, request, result)
            self._memory[session_key].append(
                ConversationTurn(member=message.content[:1200], assistant=result.text[:1800])
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

    async def _send_answer(
        self,
        destination: discord.abc.Messageable,
        request: AnswerRequest,
        result: AnswerResult,
    ) -> None:
        body = result.text.strip()
        if result.used_web_search:
            body += "\n\n*External web result — not yet RWI Technician-verified.*"
        body += (
            "\n\n**Assumptions:** Level 40 · SHD "
            f"{result.assumptions.shd} · Expertise {result.assumptions.expertise} · "
            f"{result.assumptions.mode} · maximum rolls"
        )
        if result.citations:
            body += "\n\n**Sources**"
            for citation in result.citations[:8]:
                label = (
                    "Official"
                    if citation.official
                    else citation.source_type.replace("_", " ").title()
                )
                body += f"\n- [{citation.title}]({citation.url}) — {label}"
        chunks = split_discord_message(body)

        view: FeedbackView | None = None
        if result.cache_entry_id is not None and not result.learning_opt_out:
            cache_id = result.cache_entry_id

            async def helpful() -> None:
                state = await self.bot.services.cache.mark_feedback(cache_id, helpful=True)
                await self.bot.services.audit.record(
                    AuditRecord(
                        event_type="cache.feedback_helpful",
                        actor_id=request.user_id,
                        target_type="answer_cache",
                        target_id=str(cache_id),
                        details={"state": state.value, "is_dm": request.is_dm},
                    )
                )

            async def incorrect() -> None:
                state = await self.bot.services.cache.mark_feedback(cache_id, helpful=False)
                interpreted = interpret_locally(request.question)
                signature = question_signature(
                    interpreted.normalized_question,
                    assumptions=request.assumptions.model_dump(mode="json"),
                    constraints=interpreted.constraints,
                )
                ticket_id = await self.bot.services.tickets.open_or_increment(
                    signature=signature,
                    sanitized_question=sanitize_for_technicians(request.question),
                    requester_user_id=request.user_id,
                )
                await self.bot.services.audit.record(
                    AuditRecord(
                        event_type="cache.feedback_incorrect",
                        actor_id=request.user_id,
                        target_type="answer_cache",
                        target_id=str(cache_id),
                        reason="Member reported the answer as incorrect or outdated",
                        details={
                            "state": state.value,
                            "ticket_id": str(ticket_id),
                            "is_dm": request.is_dm,
                        },
                    )
                )

            view = FeedbackView(user_id=request.user_id, helpful=helpful, incorrect=incorrect)

        for index, chunk in enumerate(chunks):
            if view is not None and index == len(chunks) - 1:
                await destination.send(chunk, view=view)
            else:
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
