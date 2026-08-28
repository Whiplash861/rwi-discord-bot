from __future__ import annotations

import asyncio

from rwi_bot.application import build_services
from rwi_bot.bot.client import RwiBot
from rwi_bot.config import get_settings
from rwi_bot.logging import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    services = await build_services(settings)
    bot = RwiBot(services)
    services.audit.discord_sink = bot
    await bot.start(settings.discord_token.get_secret_value(), reconnect=True)


def cli() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
