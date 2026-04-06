"""Telegram bot entry point — polling mode."""

import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from bot.config import TELEGRAM_BOT_TOKEN
from bot.handlers.commands import start_command, menu_command, help_command, reset_command
from bot.handlers.callbacks import callback_handler
from bot.handlers.messages import message_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))

    # Callback query handler (inline buttons)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Free-text message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    return app


def run_bot():
    logger.info("Starting PayPal Credit Agent bot (polling mode)...")
    app = create_bot()
    app.run_polling(drop_pending_updates=True)
