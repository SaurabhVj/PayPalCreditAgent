"""Handler for data sent from Telegram Mini App via sendData()."""

import json
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot.services.session import set_state
from bot.models.state import FlowState
from bot.utils.formatters import scoring_message, all_offers_message
from bot.utils.keyboards import offers_keyboard


async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process data sent from the Mini App."""
    raw = update.effective_message.web_app_data
    if not raw:
        return

    try:
        data = json.loads(raw.data)
    except json.JSONDecodeError:
        return

    user_id = update.effective_user.id
    action = data.get("action")

    if action == "login_complete":
        # User logged in via Mini App — continue credit flow in bot chat
        await update.message.reply_text(
            "✅ *Connected successfully!*\n\n"
            "👤 Arun Sharma\n"
            "📧 arun.sharma@email.com\n"
            "🏦 PayPal member: 36 months\n"
            "💳 Credit band: _prime_",
            parse_mode="Markdown",
        )
        await asyncio.sleep(1)

        # Run NBA scoring
        await update.message.chat.send_action(ChatAction.TYPING)
        await update.message.reply_text(
            scoring_message(), parse_mode="Markdown",
        )
        await asyncio.sleep(2.5)

        await update.message.reply_text(
            "✅ *NBA Model complete!*\n"
            "📊 Offers matched: *3*\n"
            "⏱ Decision time: *2.8 seconds*\n"
            "🧠 Model: _nba-credit-v4.1_",
            parse_mode="Markdown",
        )
        await asyncio.sleep(1)

        set_state(user_id, FlowState.OFFERS_SHOWN)
        await update.message.reply_text(
            "🎯 Great news — the NBA Model matched you to *3 personalised offers*.\n"
            "Tap one to learn more:\n\n" + all_offers_message(),
            parse_mode="Markdown",
            reply_markup=offers_keyboard(),
        )

    elif action == "approved":
        product = data.get("product", "")
        limit = data.get("limit", "")
        await update.message.reply_text(
            f"🎊 *Approved!* Your *{product}* ({limit}) is now active.",
            parse_mode="Markdown",
        )
