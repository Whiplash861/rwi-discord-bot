from __future__ import annotations

import asyncio
import hashlib

import discord
import structlog
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.services.budget import SpendingClass
from rwi_bot.services.knowledge import sanitize_for_technicians
from rwi_bot.services.member_profiles import detect_possible_personal_information
from rwi_bot.services.video_inspection import VideoInspectionError


class CommunityLoadoutsCog(commands.Cog):
    """Indexes designated public loadout messages, including text channels and forum replies."""

    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("community_loadouts")
        self._sync_task: asyncio.Task[None] | None = None
        self._index_lock = asyncio.Lock()

    def schedule_sync(self) -> None:
        if (
            not self.bot.services.settings.community_loadout_indexing_enabled
            or self.bot.services.maintenance.halted
            or (self._sync_task is not None and not self._sync_task.done())
        ):
            return
        self._sync_task = asyncio.create_task(
            self._sync_existing(), name="rwi-community-loadout-sync"
        )

    async def cog_unload(self) -> None:
        if self._sync_task is not None:
            self._sync_task.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._index_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, _: discord.Message, after: discord.Message) -> None:
        await self._index_message(after)

    @commands.Cog.listener()
    async def on_thread_update(self, _: discord.Thread, after: discord.Thread) -> None:
        if not self._is_community_thread(after) or self.bot.services.maintenance.halted:
            return
        try:
            starter = await after.fetch_message(after.id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        await self._index_message(starter)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        if thread.guild.id != self.bot.services.settings.discord_guild_id:
            return
        async with self._index_lock:
            await self.bot.services.community_loadouts.remove_by_thread(
                guild_id=thread.guild.id,
                thread_id=thread.id,
            )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        if payload.guild_id != self.bot.services.settings.discord_guild_id:
            return
        async with self._index_lock:
            await self.bot.services.community_loadouts.remove_by_starter_message(
                guild_id=payload.guild_id,
                message_id=payload.message_id,
            )

    async def _sync_existing(self) -> None:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None or self.bot.services.maintenance.halted:
            return
        for channel in guild.channels:
            if channel.name not in names.COMMUNITY_LOADOUT_CHANNELS:
                continue
            if isinstance(channel, discord.TextChannel):
                await self._sync_history(channel)
                for thread in channel.threads:
                    await self._sync_history(thread)
            elif isinstance(channel, discord.ForumChannel):
                seen = set()
                for thread in channel.threads:
                    await self._sync_history(thread)
                    seen.add(thread.id)
                try:
                    async for thread in channel.archived_threads(limit=None):
                        if thread.id not in seen:
                            await self._sync_history(thread)
                except discord.HTTPException:
                    self.log.warning("community_archived_sync_unavailable")

    async def _sync_history(self, channel: discord.TextChannel | discord.Thread) -> None:
        try:
            async for message in channel.history(limit=None, oldest_first=True):
                if self.bot.services.maintenance.halted:
                    return
                await self._index_message(message)
        except discord.HTTPException:
            self.log.warning("loadout_history_unavailable", channel_id=channel.id)

    async def _index_message(self, message: discord.Message) -> bool:
        async with self._index_lock:
            return await self._index_message_locked(message)

    async def _index_message_locked(self, message: discord.Message) -> bool:
        settings = self.bot.services.settings
        if (
            not settings.community_loadout_indexing_enabled
            or self.bot.services.maintenance.halted
            or message.author.bot
            or message.guild is None
            or message.guild.id != settings.discord_guild_id
            or not (
                (
                    isinstance(message.channel, discord.Thread)
                    and self._is_community_thread(message.channel)
                )
                or (
                    isinstance(message.channel, discord.TextChannel)
                    and message.channel.name in names.COMMUNITY_LOADOUT_CHANNELS
                )
            )
        ):
            return False
        thread = message.channel
        assert isinstance(thread, (discord.TextChannel, discord.Thread))
        if await self.bot.services.profiles.learning_opted_out(message.author.id):
            await self.bot.services.community_loadouts.remove_by_starter_message(
                guild_id=message.guild.id,
                message_id=message.id,
            )
            return False
        title = sanitize_for_technicians(
            thread.name
            if isinstance(thread, discord.Thread)
            else (message.content.splitlines() or ["Member loadout screenshot"])[0][:200]
        )
        content = sanitize_for_technicians(message.content)
        tags = (
            [tag.name for tag in thread.applied_tags] if isinstance(thread, discord.Thread) else []
        )
        fingerprint = hashlib.sha256(
            repr((message.content, title, tags, [a.id for a in message.attachments])).encode()
        ).hexdigest()
        if await self.bot.services.community_loadouts.source_matches(
            message.guild.id, message.id, fingerprint
        ):
            return False
        # Never leave old content searchable after an edit we cannot safely index.
        await self.bot.services.community_loadouts.deactivate_source(message.guild.id, message.id)
        if detect_possible_personal_information(content):
            return False
        screenshots = [
            a for a in message.attachments if self.bot.services.video_inspection.supports_image(a)
        ]
        if screenshots:
            try:
                result = await self.bot.services.video_inspection.inspect_image(
                    screenshots[0],
                    question=(
                        "Extract only the visible Division 2 loadout: slot, item, talent, "
                        "roll, weapon and skill. Mark unreadable text unknown. No "
                        "recommendations or identities."
                    ),
                    user_id=message.author.id,
                    spending_class=SpendingClass.AUTONOMOUS_RESEARCH,
                )
                content += "\nScreenshot transcription (unverified observations):\n" + result.text
            except VideoInspectionError:
                self.log.warning("loadout_image_unavailable", message_id=message.id)
                return False
        if len(content) < 40 or detect_possible_personal_information(content):
            return False
        if await self.bot.services.profiles.learning_opted_out(message.author.id):
            return False
        if not title or not content:
            return False
        parent = thread.parent if isinstance(thread, discord.Thread) else thread
        assert isinstance(parent, (discord.ForumChannel, discord.TextChannel))
        qa = self.bot.services.qa
        written = message.edited_at or message.created_at
        await self.bot.services.community_loadouts.upsert(
            guild_id=message.guild.id,
            forum_channel_id=parent.id,
            thread_id=thread.id,
            starter_message_id=message.id,
            author_user_id=message.author.id,
            title=title,
            content=content,
            tags=tags,
            source_url=(
                f"https://discord.com/channels/{message.guild.id}/{thread.id}/{message.id}"
            ),
            game_version=qa.current_game_version
            if written.date() >= qa.current_game_version_started_on
            else "historical-unreviewed",
            submitted_at=message.created_at,
            source_fingerprint=fingerprint,
        )
        return True

    @staticmethod
    def _is_starter_message(message: discord.Message) -> bool:
        return isinstance(message.channel, discord.Thread) and message.id == message.channel.id

    @staticmethod
    def _is_community_thread(thread: discord.Thread) -> bool:
        return (
            isinstance(thread.parent, (discord.ForumChannel, discord.TextChannel))
            and thread.parent.name in names.COMMUNITY_LOADOUT_CHANNELS
        )
