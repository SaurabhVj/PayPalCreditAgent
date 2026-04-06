"""Handler for data sent from Telegram Mini App via sendData()."""

from telegram import Update
from telegram.ext import ContextTypes


async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process data sent from the Mini App."""
    data = update.effective_message.web_app_data
    if data:
        await update.message.reply_text(
            f"Received from Mini App: {data.data}"
        )
