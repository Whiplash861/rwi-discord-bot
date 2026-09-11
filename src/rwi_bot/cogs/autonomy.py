from __future__ import annotations

from datetime import UTC, datetime

import discord
import structlog
from discord.ext import commands, tasks

from rwi_bot.bot import names
from rwi_bot.bot.client import RwiBot
from rwi_bot.bot.server_blueprint import CATEGORY_CHANNELS, ServerReconciler
from rwi_bot.services.announcements import announcement_key
from rwi_bot.services.autonomous_research import AutonomousResearchOutcome
from rwi_bot.services.knowledge import sanitize_for_technicians


class AutonomyCog(commands.Cog):
    def __init__(self, bot: RwiBot) -> None:
        self.bot = bot
        self.log = structlog.get_logger("autonomy")
        self.monitor_game_updates.change_interval(
            hours=bot.services.settings.autonomous_research_interval_hours
        )

    async def cog_unload(self) -> None:
        self.monitor_game_updates.cancel()

    def schedule_start(self) -> None:
        settings = self.bot.services.settings
        if (
            not settings.autonomous_research_enabled
            or self.bot.services.maintenance.halted
            or self.monitor_game_updates.is_running()
        ):
            return
        self.monitor_game_updates.start()

    @tasks.loop(hours=6, reconnect=True)
    async def monitor_game_updates(self) -> None:
        if self.bot.services.maintenance.halted:
            return
        try:
            outcome = await self.bot.services.autonomous_research.run_once()
        except Exception:
            self.log.exception("scheduled_game_research_failed")
            return
        self.log.info(
            "scheduled_game_research_complete",
            correlation_id=str(outcome.correlation_id),
            season_changed=outcome.season_changed,
            promoted=outcome.promoted,
            staged=outcome.staged,
            duplicates=outcome.duplicates,
        )
        try:
            await self.publish_announcements(outcome)
        except Exception:
            self.log.exception("game_announcement_publish_failed")

    async def publish_announcements(self, outcome: AutonomousResearchOutcome) -> int:
        if self.bot.services.maintenance.halted:
            return 0
        channel = await self.ensure_announcement_space()
        if channel is None:
            return 0
        return await self._publish_to_channel(channel, outcome)

    async def ensure_announcement_space(self) -> discord.TextChannel | None:
        guild = self.bot.get_guild(self.bot.services.settings.discord_guild_id)
        if guild is None:
            return None
        spec = next(
            s for s in CATEGORY_CHANNELS[names.ALLIANCE_HUB] if s.name == names.GAME_UPDATES
        )
        channel = await ServerReconciler(guild).ensure_channel(names.ALLIANCE_HUB, spec)
        if not isinstance(channel, discord.TextChannel):
            return None
        return channel

    async def _publish_to_channel(
        self, channel: discord.TextChannel, outcome: AutonomousResearchOutcome
    ) -> int:
        existing: set[str] = set()
        async for message in channel.history(limit=200):
            if self.bot.user and message.author.id == self.bot.user.id:
                existing.update(e.footer.text for e in message.embeds if e.footer.text)
        published = 0
        for finding in outcome.findings:
            key = announcement_key(finding, outcome.citations, today=datetime.now(UTC).date())
            marker = f"ERIN_GAME_UPDATE:{key}"
            if key is None or marker in existing or published >= 4:
                continue
            clean = (
                sanitize_for_technicians(finding.summary)
                .replace("@everyone", "everyone")
                .replace("@here", "here")
            )
            embed = discord.Embed(
                title=f"Division 2 — {finding.subject}"[:250],
                description=clean[:2000],
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="Developer announcement",
                value="\n".join(str(url) for url in finding.source_urls[:2])[:1000],
                inline=False,
            )
            embed.add_field(
                name="Published", value=str(finding.context["published_on"]), inline=True
            )
            embed.set_footer(text=marker)
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            existing.add(marker)
            published += 1
        return published

    @monitor_game_updates.before_loop
    async def before_monitor_game_updates(self) -> None:
        await self.bot.wait_until_ready()
