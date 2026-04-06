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
        # User logged in via Mini App — use their entered name/email
        user_name = data.get("user", "User")
        user_email = data.get("email", "user@email.com")

        # Store in session for later use
        from bot.services.session import get_session
        session = get_session(user_id)
        session["name"] = user_name
        session["email"] = user_email
        session["awaiting_login"] = False

        # Show connected confirmation
        await update.message.reply_text(
            f"✅ *PayPal account connected!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 *{user_name}*\n"
            f"📧 {user_email}\n"
            f"🏦 PayPal member: 36 months\n"
            f"💳 Credit band: _prime_\n\n"
            f"_Starting credit assessment..._",
            parse_mode="Markdown",
        )
        await asyncio.sleep(1.5)

        # Run NBA scoring
        await update.message.chat.send_action(ChatAction.TYPING)
        await update.message.reply_text(
            f"🧠 *Analyzing {user_name}'s profile...*\n\n"
            f"👤 {user_name}\n"
            f"📧 {user_email}\n"
            f"📅 PayPal member: 36 months\n"
            f"💳 Credit band: _prime_\n"
            f"💰 Avg monthly spend: $4,200\n\n"
            f"_Running NBA model..._",
            parse_mode="Markdown",
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
            f"🎯 Great news, {user_name} — the NBA Model matched you to *3 personalised offers*.\n"
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
