"""Single entry point — starts Telegram bot + FastAPI server together."""

import asyncio
import logging
import uvicorn
from bot.main import create_bot
from bot.config import TELEGRAM_BOT_TOKEN, API_PORT

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    # Start bot
    bot_app = create_bot()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram bot started (polling mode)")

    # Start FastAPI
    config = uvicorn.Config(
        "api.server:app",
        host="0.0.0.0",
        port=API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info(f"FastAPI server starting on port {API_PORT}")

    try:
        await server.serve()
    finally:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
