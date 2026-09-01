from __future__ import annotations

import structlog
from discord.ext import commands, tasks

from rwi_bot.bot.client import RwiBot


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

    @monitor_game_updates.before_loop
    async def before_monitor_game_updates(self) -> None:
        await self.bot.wait_until_ready()
