from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import discord
import structlog
from discord.ext import commands

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.server_blueprint import CATEGORY_CHANNELS, ChannelSpec, ServerReconciler
from rwi_bot.data.releases import RELEASES
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.releases import (
    DeploymentSnapshot,
    Release,
    ReleaseSection,
    automatic_release,
    deployment_snapshot,
    release_marker,
    render_release_description,
)


class ReleaseNotesCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("release_notes")
        self._task: asyncio.Task[int] | None = None
        self._lock = asyncio.Lock()

    def schedule_publish(self) -> None:
        if self.bot.services.maintenance.halted or (
            self._task is not None and not self._task.done()
        ):
            return
        self._task = asyncio.create_task(
            self.publish_pending(), name="erin-release-notes-publisher"
        )

    async def cog_unload(self) -> None:
        if self._task is not None:
            self._task.cancel()

    async def publish_pending(self) -> int:
        if self.bot.services.maintenance.halted:
            return 0
        async with self._lock:
            guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
            if guild is None:
                return 0
            try:
                channel = await ServerReconciler(guild).ensure_channel(
                    names.ALLIANCE_HUB,
                    _patch_notes_spec(),
                )
            except (discord.Forbidden, discord.HTTPException, PermissionError, RuntimeError):
                self.log.exception("patch_notes_channel_unavailable")
                return 0
            if not isinstance(channel, discord.TextChannel):
                self.log.error("patch_notes_channel_wrong_type")
                return 0

            snapshot = deployment_snapshot()
            published = 0
            pending: list[Release] = []
            for release in RELEASES:
                published_version = (
                    await self.bot.services.release_history.published_version_in_channel(
                        release.all_release_ids,
                        channel.id,
                    )
                )
                if published_version != release.version:
                    pending.append(release)
            if pending:
                for release in pending:
                    if await self._publish(channel, release, snapshot):
                        published += 1
            else:
                previous = await self.bot.services.release_history.latest_deployment()
                if previous is None or previous.fingerprint != snapshot.fingerprint:
                    generated = automatic_release(
                        snapshot,
                        previous,
                        released_on=datetime.now(UTC).date(),
                    )
                    if not await self.bot.services.release_history.published_in_channel(
                        generated.release_id, channel.id
                    ) and await self._publish(channel, generated, snapshot):
                        published += 1
            self.log.info(
                "release_publish_complete",
                channel=names.ERIN_PATCH_NOTES,
                published=published,
            )
            return published

    async def _publish(
        self,
        channel: discord.TextChannel,
        release: Release,
        snapshot: DeploymentSnapshot,
    ) -> bool:
        markers = tuple(release_marker(release_id) for release_id in release.all_release_ids)
        existing = await self._find_existing(channel, markers)
        message = existing
        changed = False
        embed = release_embed(release)
        if message is None:
            message = await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            changed = True
        elif not _message_matches_release(message, embed):
            await message.edit(embed=embed)
            changed = True
        await self.bot.services.audit.record(
            AuditRecord(
                event_type="release.published",
                actor_id=self.bot.user.id if self.bot.user else None,
                target_type="erin_release",
                target_id=release.release_id,
                reason="Automatic deployment release announcement",
                details={
                    "channel_id": channel.id,
                    "message_id": message.id,
                    "update_number": release.update_number,
                    "version": release.version,
                    "released_on": release.released_on.isoformat(),
                    "automatic": release.automatic,
                    "deployment_fingerprint": snapshot.fingerprint,
                    "module_hashes": snapshot.module_hashes,
                    "recovered_existing_message": existing is not None,
                },
            )
        )
        return changed

    async def _find_existing(
        self,
        channel: discord.TextChannel,
        markers: tuple[str, ...],
    ) -> discord.Message | None:
        try:
            async for message in channel.history(limit=250):
                if message.author != self.bot.user:
                    continue
                if any((embed.footer.text or "") in markers for embed in message.embeds):
                    return message
        except (discord.Forbidden, discord.HTTPException):
            self.log.warning("patch_notes_history_unavailable")
        return None


def release_embed(release: Release) -> discord.Embed:
    colour = (
        discord.Colour.red()
        if any(note.section == ReleaseSection.CRITICAL for note in release.notes)
        else discord.Colour.orange()
    )
    embed = discord.Embed(
        title=f"ERIN Update {release.update_number}",
        description=render_release_description(release),
        colour=colour,
    )
    embed.set_footer(text=release_marker(release.release_id))
    return embed


def _message_matches_release(message: discord.Message, expected: discord.Embed) -> bool:
    if len(message.embeds) != 1:
        return False
    actual = message.embeds[0]
    return (
        actual.title == expected.title
        and actual.description == expected.description
        and actual.colour == expected.colour
        and actual.footer.text == expected.footer.text
    )


def _patch_notes_spec() -> ChannelSpec:
    return next(
        spec
        for spec in CATEGORY_CHANNELS[names.ALLIANCE_HUB]
        if spec.name == names.ERIN_PATCH_NOTES
    )
