"""Free-text message handler — uses LLM function calling for routing."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot.utils.keyboards import main_menu_keyboard, credit_menu_keyboard, offers_keyboard, portfolio_keyboard, collections_keyboard
from bot.utils.formatters import (
    balance_message, statement_message, portfolio_message,
    collections_message, all_offers_message, rewards_message,
)
from bot.services.session import (
    get_state, set_state, get_session,
    add_message, get_messages, get_proactive_context,
)
from bot.services.user_store import store_user
from bot.models.state import FlowState
from bot.config import WEBAPP_URL


async def _poll_login_from_message(update: Update, user_id: int):
    """Background poll for login completion — triggered from free-text."""
    import asyncio, httpx, logging
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
                        f"✅ *PayPal account connected!*\n\n"
                        f"👤 *{data['name']}*\n"
                        f"📧 {data['email']}\n"
                        f"🏦 PayPal member: 36 months\n"
                        f"💳 Eligibility: _Pre-qualified_",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(1)

                    await update.message.reply_text(
                        f"🔍 *Analyzing your profile...*\n\n"
                        f"Reviewing your PayPal history to find the\n"
                        f"best credit products for you.\n\n"
                        f"_This will only take a moment..._",
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
                    name = data['name']
                    set_state(user_id, FlowState.OFFERS_SHOWN)
                    await update.message.reply_text(
                        f"🎯 Great news, {name} — we found *3 personalised offers* for you.\n"
                        "Tap one to learn more:\n\n" + all_offers_message(),
                        parse_mode="Markdown",
                        reply_markup=offers_keyboard(),
                    )
                    return
        except Exception as e:
            pass


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    user = update.effective_user
    user_id = user.id

    if user.username:
        store_user(user.username.lower(), user_id)

    add_message(user_id, "user", text)
    await update.message.chat.send_action(ChatAction.TYPING)

    session = get_session(user_id)
    user_name = session.get("name", user.first_name or "")
    user_email = session.get("email", "")
    history = get_messages(user_id)
    proactive_ctx = get_proactive_context(user_id)

    # Call LLM with function calling
    from bot.services.llm_service import ask_llm
    result = await ask_llm(
        text,
        conversation_history=history,
        user_name=user_name,
        user_email=user_email,
        proactive_context=proactive_ctx,
    )

    llm_message = result.get("message")
    tool_call = result.get("tool_call")

    # Send LLM's text message (if any and no tool handles it)
    if llm_message and tool_call is None:
        await update.message.reply_text(llm_message)
        add_message(user_id, "assistant", llm_message)

    # Handle tool call
    if tool_call:
        name = tool_call["name"]
        args = tool_call.get("args", {})

        # Show LLM message before the tool result (if any)
        if llm_message:
            await update.message.reply_text(llm_message)
            add_message(user_id, "assistant", llm_message)

        if name == "search_products":
            query = args.get("query", text)
            from bot.agents.shopping_agent import search_products
            cards = await search_products(query, user_id)
            if not cards:
                await update.message.reply_text("🔍 No products found. Try a different search term.")
                add_message(user_id, "assistant", f"Searched for '{query}' — no results found.")
            else:
                await update.message.reply_text(f"🔍 Found {len(cards)} result(s):")
                shown = ", ".join(f"{c['name']} (${c['price']})" for c in cards)
                add_message(user_id, "assistant", f"Showed {len(cards)} products for '{query}': {shown}")
                session["last_search"] = query

                for card in cards:
                    sent = False
                    if card.get("image"):
                        try:
                            await update.message.reply_photo(
                                photo=card["image"],
                                caption=card["caption"],
                                parse_mode="Markdown",
                                reply_markup=card["keyboard"],
                            )
                            sent = True
                        except Exception:
                            pass
                    if not sent:
                        await update.message.reply_text(
                            f"{card['icon']} {card['caption']}",
                            parse_mode="Markdown",
                            reply_markup=card["keyboard"],
                        )

        elif name == "show_menu":
            display_name = user_name or user.first_name or "there"
            await update.message.reply_text(
                f"👋 Hi {display_name}! I'm your PayPal Assistant.\n\n"
                "I can help you with *shopping*, *credit cards*, *rewards*, and more.\n\n"
                "Choose an option or just tell me what you need:",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )

        elif name == "show_cart":
            from bot.agents.shopping_agent import get_cart_message
            msg, kb = get_cart_message(user_id)
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

        elif name == "apply_for_credit":
            import asyncio
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
            if WEBAPP_URL and WEBAPP_URL.startswith("https://"):
                asyncio.create_task(_poll_login_from_message(update, user_id))

        elif name == "show_credit_menu":
            await update.message.reply_text(
                "💳 *Credit Services*\n\nWhat would you like to do?",
                parse_mode="Markdown",
                reply_markup=credit_menu_keyboard(),
            )

        elif name == "check_balance":
            await update.message.reply_text(balance_message(), parse_mode="Markdown")

        elif name == "show_portfolio":
            await update.message.reply_text(
                portfolio_message(), parse_mode="Markdown",
                reply_markup=portfolio_keyboard(),
            )

        elif name == "show_collections":
            await update.message.reply_text(
                collections_message(), parse_mode="Markdown",
                reply_markup=collections_keyboard(),
            )

        elif name == "show_rewards":
            await update.message.reply_text(rewards_message(), parse_mode="Markdown")

    # If neither message nor tool call — fallback
    if not llm_message and not tool_call:
        await update.message.reply_text(
            "I'm not sure I understand. Here's what I can help with:",
            reply_markup=main_menu_keyboard(),
        )
