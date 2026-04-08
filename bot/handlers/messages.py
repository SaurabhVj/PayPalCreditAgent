"""Free-text message handler — LLM-first with conversation history."""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot.utils.keyboards import main_menu_keyboard, offers_keyboard, portfolio_keyboard, collections_keyboard
from bot.utils.formatters import (
    balance_message, statement_message, portfolio_message,
    collections_message, all_offers_message,
)
from bot.services.session import (
    get_state, set_state, get_session,
    add_message, get_messages, get_proactive_context,
)
from bot.services.user_store import store_user
from bot.models.state import FlowState


async def _poll_login_from_message(update: Update, user_id: int):
    """Background poll for login completion — triggered from free-text."""
    import asyncio, httpx, logging
    from bot.config import WEBAPP_URL
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    logger = logging.getLogger(__name__)

    for _ in range(30):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/login-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    session = get_session(user_id)
                    session["name"] = data["name"]
                    session["email"] = data["email"]

                    await update.message.reply_text(
                        f"✅ *PayPal account connected!*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 *{data['name']}*\n"
                        f"📧 {data['email']}\n"
                        f"🏦 PayPal member: 36 months\n"
                        f"💳 Eligibility: _Pre-qualified_",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(1)

                    form_url = f"{WEBAPP_URL}/webapp?mode=form&name={data['name']}&email={data['email']}"
                    await update.message.reply_text(
                        "📋 *Application Pre-filled*\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "19 of 20 fields filled from your PayPal profile.\n\n"
                        "✏️ *Missing: PAN / SSN last 4 digits*\n\n"
                        "_Tap below to review and complete:_",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📝 Complete Application", web_app=WebAppInfo(url=form_url))],
                        ]),
                    )

                    # Poll for form
                    asyncio.create_task(_poll_form_from_message(update, user_id))
                    return
        except Exception as e:
            logger.debug(f"Login poll error: {e}")


async def _poll_form_from_message(update: Update, user_id: int):
    """Background poll for form completion — triggered from free-text."""
    import asyncio, httpx, logging
    from bot.config import WEBAPP_URL
    from bot.utils.formatters import all_offers_message
    logger = logging.getLogger(__name__)

    for _ in range(60):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/form-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    name = get_session(user_id).get("name", "User")
                    await update.message.reply_text(
                        "✅ *Application form complete!* All 20 fields confirmed.\n\n"
                        f"🔍 _Analyzing {name}'s profile..._",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(2.5)
                    await update.message.reply_text(
                        "✅ *Analysis complete!*\n"
                        "📊 Offers matched: *3*\n"
                        "⏱ Response time: *2.8 seconds*",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(1)
                    set_state(user_id, FlowState.OFFERS_SHOWN)
                    await update.message.reply_text(
                        f"🎯 Great news, {name} — we found *3 personalised offers* for you.\n"
                        "Tap one to learn more:\n\n" + all_offers_message(),
                        parse_mode="Markdown",
                        reply_markup=offers_keyboard(),
                    )
                    return
        except Exception as e:
            logger.debug(f"Form poll error: {e}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    user = update.effective_user
    user_id = user.id

    # Store username → chat_id mapping for proactive messages
    if user.username:
        store_user(user.username.lower(), user_id)

    # Store user message in conversation history
    add_message(user_id, "user", text)

    await update.message.chat.send_action(ChatAction.TYPING)

    # Get session context
    session = get_session(user_id)
    user_name = session.get("name", user.first_name or "")
    user_email = session.get("email", "")
    history = get_messages(user_id)
    proactive_ctx = get_proactive_context(user_id)

    # Try LLM with full context
    from bot.services.llm_service import ask_llm, parse_action
    llm_response = await ask_llm(
        text,
        conversation_history=history,
        user_name=user_name,
        user_email=user_email,
        proactive_context=proactive_ctx,
    )

    if llm_response:
        action, clean_msg = parse_action(llm_response)

        # Send the LLM's message (if any)
        if clean_msg:
            await update.message.reply_text(clean_msg)
            # Store bot response in history
            add_message(user_id, "assistant", clean_msg)

        # Trigger workflow if action detected — same flows as buttons
        if action == "credit":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
            from bot.config import WEBAPP_URL
            login_url = f"{WEBAPP_URL}/webapp?mode=login"
            await update.message.reply_text(
                "🔐 *Connect PayPal*\n"
                "━━━━━━━━━━━━━━━━━\n"
                "Sign in with your PayPal account to unlock\n"
                "personalised credit offers.\n\n"
                "🔒 Secure OAuth — we never see your password.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Connect with PayPal", web_app=WebAppInfo(url=login_url))],
                ]) if WEBAPP_URL and WEBAPP_URL.startswith("https://") else offers_keyboard(),
            )
            import asyncio
            from bot.handlers.callbacks import _poll_login
            if WEBAPP_URL and WEBAPP_URL.startswith("https://"):
                asyncio.create_task(_poll_login_from_message(update, user_id))
        elif action == "balance":
            await update.message.reply_text(
                balance_message(), parse_mode="Markdown",
            )
        elif action == "portfolio":
            await update.message.reply_text(
                portfolio_message(), parse_mode="Markdown",
                reply_markup=portfolio_keyboard(),
            )
        elif action == "collections":
            await update.message.reply_text(
                collections_message(), parse_mode="Markdown",
                reply_markup=collections_keyboard(),
            )
        elif action == "menu":
            await update.message.reply_text(
                "Choose an option:", reply_markup=main_menu_keyboard(),
            )
    else:
        # LLM failed — show menu as fallback
        await update.message.reply_text(
            "I'm not sure I understand. Here's what I can help with:",
            reply_markup=main_menu_keyboard(),
        )
