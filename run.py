"""Single entry point — starts Telegram bot + FastAPI server together."""

import asyncio
import logging
import os
import uvicorn
import httpx
from bot.main import create_bot
from bot.config import TELEGRAM_BOT_TOKEN, API_PORT, WEBAPP_URL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    # Wait for old instance to shut down (Render zero-downtime deploy overlap)
    logger.info("Waiting 15s for old instance to release polling...")
    await asyncio.sleep(15)

    # Start bot
    bot_app = create_bot()
    await bot_app.initialize()
    await bot_app.start()
    # Initialize database
    from bot.config import DATABASE_URL
    if DATABASE_URL:
        try:
            from bot.services.database import get_pool
            await get_pool()
            logger.info("Database connected")
        except Exception as e:
            logger.warning(f"Database init failed (continuing without DB): {e}")

    await bot_app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("Telegram bot started (polling mode)")

    # Start proactive offer detection engine
    from bot.services.proactive import proactive_loop
    asyncio.create_task(proactive_loop(bot_app.bot))
    logger.info("Proactive detection engine started")

    # Start FastAPI
    config = uvicorn.Config(
        "api.server:app",
        host="0.0.0.0",
        port=API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info(f"FastAPI server starting on port {API_PORT}")

    # Start self-ping to keep Render free tier awake
    asyncio.create_task(keep_alive())

    try:
        await server.serve()
    finally:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


async def keep_alive():
    """Ping own health endpoint every 10 min to prevent Render free tier sleep."""
    url = f"{WEBAPP_URL}/api/health" if WEBAPP_URL.startswith("http") else f"http://localhost:{API_PORT}/api/health"
    while True:
        await asyncio.sleep(600)  # 10 minutes
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                logger.info(f"Keep-alive ping: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Keep-alive failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
