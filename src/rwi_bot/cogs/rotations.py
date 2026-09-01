from __future__ import annotations

import asyncio
from dataclasses import dataclass

import discord
import structlog
from discord.ext import commands, tasks

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.server_blueprint import CATEGORY_CHANNELS, ServerReconciler
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.rotations import RotationPublication


@dataclass(frozen=True, slots=True)
class RotationPublishOutcome:
    changed: int
    total: int
    warnings: tuple[str, ...]
    summary: str


class RotationsCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("rotations")
        self._lock = asyncio.Lock()
        self.refresh_rotation_posts.change_interval(
            minutes=bot.services.settings.rotation_refresh_minutes
        )

    async def cog_unload(self) -> None:
        self.refresh_rotation_posts.cancel()

    def schedule_start(self) -> None:
        settings = self.bot.services.settings
        if (
            not settings.rotation_updates_enabled
            or self.bot.services.maintenance.halted
            or self.refresh_rotation_posts.is_running()
        ):
            return
        self.refresh_rotation_posts.start()

    async def ensure_rotation_space(self) -> dict[str, discord.TextChannel]:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None:
            return {}
        reconciler = ServerReconciler(guild)
        channels: dict[str, discord.TextChannel] = {}
        for spec in CATEGORY_CHANNELS[names.ROTATIONS]:
            try:
                channel = await reconciler.ensure_channel(names.ROTATIONS, spec)
            except (discord.Forbidden, discord.HTTPException, PermissionError, RuntimeError):
                self.log.exception("rotation_channel_unavailable", channel=spec.name)
                continue
            if isinstance(channel, discord.TextChannel):
                channels[channel.name] = channel
        if channels:
            self.log.info(
                "rotation_space_ready",
                category=names.ROTATIONS,
                channels=sorted(channels),
            )
        return channels

    async def refresh_now(self, *, force_web: bool = False) -> RotationPublishOutcome:
        async with self._lock:
            channels = await self.ensure_rotation_space()
            if len(channels) != len(names.ROTATION_CHANNELS):
                raise RuntimeError("One or more rotation channels are unavailable.")
            snapshot = await self.bot.services.rotations.collect(force_web=force_web)
            changed = 0
            for publication in snapshot.publications:
                channel = channels.get(publication.channel_name)
                if channel is None:
                    continue
                if await self._publish(channel, publication):
                    changed += 1
            state = await self.bot.services.rotations.status()
            if changed:
                await self.bot.services.audit.record(
                    AuditRecord(
                        event_type="rotation.published",
                        actor_id=self.bot.user.id if self.bot.user else None,
                        target_type="rotation_index",
                        target_id=str(snapshot.correlation_id),
                        reason=state.last_summary,
                        correlation_id=snapshot.correlation_id,
                        details={
                            "changed_posts": changed,
                            "total_posts": len(snapshot.publications),
                            "warnings": list(snapshot.warnings),
                            "web_researched": snapshot.web_researched,
                            "used_cached_web": snapshot.used_cached_web,
                        },
                    )
                )
            if snapshot.warnings:
                self.log.warning(
                    "rotation_refresh_partial",
                    warnings=list(snapshot.warnings),
                    correlation_id=str(snapshot.correlation_id),
                )
            self.log.info(
                "rotation_refresh_complete",
                changed=changed,
                total=len(snapshot.publications),
                web_researched=snapshot.web_researched,
            )
            return RotationPublishOutcome(
                changed=changed,
                total=len(snapshot.publications),
                warnings=snapshot.warnings,
                summary=state.last_summary,
            )

    @tasks.loop(minutes=60, reconnect=True)
    async def refresh_rotation_posts(self) -> None:
        if self.bot.services.maintenance.halted:
            return
        try:
            await self.refresh_now()
        except Exception as exc:
            self.log.exception("scheduled_rotation_refresh_failed")
            await self.bot.services.audit.record(
                AuditRecord(
                    event_type="rotation.refresh_failed",
                    actor_id=self.bot.user.id if self.bot.user else None,
                    target_type="rotation_index",
                    reason=(
                        "ERIN could not refresh the rotation channels; existing posts were "
                        "left unchanged."
                    ),
                    details={"error_type": type(exc).__name__},
                )
            )

    @refresh_rotation_posts.before_loop
    async def before_refresh_rotation_posts(self) -> None:
        await self.bot.wait_until_ready()

    async def _publish(
        self,
        channel: discord.TextChannel,
        publication: RotationPublication,
    ) -> bool:
        embeds = rotation_embeds(publication)
        existing = await self._find_existing(channel, publication.marker)
        if existing is not None and _message_matches(existing, embeds):
            return False
        if existing is None:
            message = await channel.send(
                embeds=embeds,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            try:
                await message.pin(reason="Keep ERIN's current rotation index visible")
            except (discord.Forbidden, discord.HTTPException):
                pass
            return True
        await existing.edit(embeds=embeds, allowed_mentions=discord.AllowedMentions.none())
        return True

    async def _find_existing(
        self,
        channel: discord.TextChannel,
        marker: str,
    ) -> discord.Message | None:
        try:
            async for message in channel.history(limit=50):
                if message.author != self.bot.user:
                    continue
                if any(embed.footer.text == marker for embed in message.embeds):
                    return message
        except (discord.Forbidden, discord.HTTPException):
            self.log.warning("rotation_history_unavailable", channel=channel.name)
        return None


def rotation_embed(publication: RotationPublication) -> discord.Embed:
    embed = discord.Embed(
        title=publication.title,
        description=publication.description,
        colour=discord.Colour.orange(),
    )
    for field in publication.fields[:25]:
        embed.add_field(
            name=field.name[:256],
            value=field.value[:1024],
            inline=field.inline,
        )
    embed.set_footer(text=publication.marker)
    return embed


def rotation_embeds(publication: RotationPublication) -> list[discord.Embed]:
    embeds = [rotation_embed(publication)]
    for image in publication.images[:9]:
        map_embed = discord.Embed(
            title=image.label,
            colour=discord.Colour.orange(),
        )
        map_embed.set_image(url=image.url)
        embeds.append(map_embed)
    return embeds


def _message_matches(message: discord.Message, expected: list[discord.Embed]) -> bool:
    if len(message.embeds) != len(expected):
        return False
    return [embed.to_dict() for embed in message.embeds] == [embed.to_dict() for embed in expected]
