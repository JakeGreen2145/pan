import asyncio
import sys

import structlog

from pan.agents.registry import init_agents
from pan.config.logging import configure_logging
from pan.config.settings import get_settings
from pan.interface.discord_bot import PanBot
from pan.orchestration.scheduler import PanScheduler
from pan.orchestration.supervisor import build_supervisor_graph
from pan.services.checkpointer import close_checkpointer, init_checkpointer
from pan.services.database import close_database, init_database
from pan.services.redis import RedisService


async def main() -> None:
    settings = get_settings()

    configure_logging(
        log_level=settings.log_level,
        json_output=not settings.debug,
    )
    logger = structlog.get_logger()
    logger.info("pan_starting", debug=settings.debug)

    await init_database(settings.db)

    redis = RedisService(settings.redis)
    await redis.connect()

    checkpointer = await init_checkpointer(settings.db.psycopg_url)

    await init_agents()

    graph = build_supervisor_graph(checkpointer)
    logger.info("supervisor_graph_ready")

    scheduler = PanScheduler(graph)
    await scheduler.start()

    bot = PanBot(settings.discord, graph)

    try:
        logger.info("starting_discord_bot")
        await bot.start(settings.discord.token.get_secret_value())
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    finally:
        logger.info("pan_shutting_down")

        if not bot.is_closed():
            await bot.close()

        await scheduler.stop()
        await redis.close()
        await close_checkpointer()
        await close_database()

        logger.info("pan_shutdown_complete")


def run() -> None:
    try:
        import uvloop

        uvloop.install()
    except ImportError:
        pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run()
