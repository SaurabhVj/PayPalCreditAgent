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

        # Trigger workflow if action detected
        if action == "credit":
            set_state(user_id, FlowState.OFFERS_SHOWN)
            await update.message.reply_text(
                all_offers_message(), parse_mode="Markdown",
                reply_markup=offers_keyboard(),
            )
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
