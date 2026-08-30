from __future__ import annotations

import asyncio

import discord
import structlog
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.services.knowledge import sanitize_for_technicians


class CommunityLoadoutsCog(commands.Cog):
    """Indexes only public Community Builds forum starter posts."""

    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("community_loadouts")
        self._sync_task: asyncio.Task[None] | None = None

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
        if self._is_starter_message(message):
            await self._index_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, _: discord.Message, after: discord.Message) -> None:
        if self._is_starter_message(after):
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
        await self.bot.services.community_loadouts.remove_by_thread(
            guild_id=thread.guild.id,
            thread_id=thread.id,
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        if payload.guild_id != self.bot.services.settings.discord_guild_id:
            return
        await self.bot.services.community_loadouts.remove_by_starter_message(
            guild_id=payload.guild_id,
            message_id=payload.message_id,
        )

    async def _sync_existing(self) -> None:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None or self.bot.services.maintenance.halted:
            return
        forum = next(
            (
                channel
                for channel in guild.channels
                if isinstance(channel, discord.ForumChannel)
                and channel.name in names.COMMUNITY_LOADOUT_CHANNELS
            ),
            None,
        )
        if forum is None:
            self.log.info("community_forum_unavailable")
            return

        threads: list[discord.Thread] = list(forum.threads[:100])
        remaining = 100 - len(threads)
        if remaining > 0:
            try:
                async for thread in forum.archived_threads(limit=remaining):
                    threads.append(thread)
            except (discord.Forbidden, discord.HTTPException):
                self.log.warning("community_archived_sync_unavailable")

        indexed = 0
        for thread in threads:
            if self.bot.services.maintenance.halted:
                return
            try:
                starter = await thread.fetch_message(thread.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
            if await self._index_message(starter):
                indexed += 1
        self.log.info("community_sync_complete", indexed=indexed, examined=len(threads))

    async def _index_message(self, message: discord.Message) -> bool:
        settings = self.bot.services.settings
        if (
            not settings.community_loadout_indexing_enabled
            or self.bot.services.maintenance.halted
            or message.author.bot
            or message.guild is None
            or message.guild.id != settings.discord_guild_id
            or not isinstance(message.channel, discord.Thread)
            or not self._is_community_thread(message.channel)
        ):
            return False
        thread = message.channel
        if await self.bot.services.profiles.learning_opted_out(message.author.id):
            await self.bot.services.community_loadouts.remove_by_thread(
                guild_id=message.guild.id,
                thread_id=thread.id,
            )
            return False
        title = sanitize_for_technicians(thread.name)
        content = sanitize_for_technicians(message.content)
        if not title or not content:
            return False
        parent = thread.parent
        assert isinstance(parent, discord.ForumChannel)
        await self.bot.services.community_loadouts.upsert(
            guild_id=message.guild.id,
            forum_channel_id=parent.id,
            thread_id=thread.id,
            starter_message_id=message.id,
            author_user_id=message.author.id,
            title=title,
            content=content,
            tags=[tag.name for tag in thread.applied_tags],
            source_url=(
                f"https://discord.com/channels/{message.guild.id}/{thread.id}/{message.id}"
            ),
            game_version=settings.current_game_version,
            submitted_at=message.created_at,
        )
        return True

    @staticmethod
    def _is_starter_message(message: discord.Message) -> bool:
        return isinstance(message.channel, discord.Thread) and message.id == message.channel.id

    @staticmethod
    def _is_community_thread(thread: discord.Thread) -> bool:
        return (
            isinstance(thread.parent, discord.ForumChannel)
            and thread.parent.name in names.COMMUNITY_LOADOUT_CHANNELS
        )
