"""Free-text message handler — thin dispatcher to Orchestrator."""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot.utils.keyboards import main_menu_keyboard, credit_menu_keyboard, portfolio_keyboard, collections_keyboard
from bot.utils.formatters import (
    balance_message, rewards_message, portfolio_message,
    collections_message, all_offers_message,
)
from bot.services.session import get_session, add_message, get_messages, get_proactive_context
from bot.services.user_store import store_user
from bot.models.state import FlowState
from bot.config import WEBAPP_URL

logger = logging.getLogger(__name__)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    user = update.effective_user
    user_id = user.id

    # Store user in cache + DB
    if user.username:
        store_user(user.username.lower(), user_id)
    try:
        from bot.services.user_store import store_user_db
        await store_user_db(user_id, user.username or "", user.first_name or "", "")
    except Exception:
        pass

    # Store message in session + DB
    add_message(user_id, "user", text)
    try:
        from bot.services.database import add_message as db_add_msg
        await db_add_msg(user_id, "user", text)
    except Exception:
        pass

    await update.message.chat.send_action(ChatAction.TYPING)

    # Get context
    session = get_session(user_id)
    history = get_messages(user_id)

    # Route through Orchestrator
    from bot.orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    result = await orchestrator.process(text, user_id, history, session)

    # ── Render the result ──

    # 1. Show menu
    if result.show_menu:
        display_name = session.get("name") or user.first_name or "there"
        await update.message.reply_text(
            f"👋 Hi {display_name}! I'm your PayPal Assistant.\n\n"
            "I can help you with *shopping*, *credit cards*, *rewards*, and more.\n\n"
            "Choose an option or just tell me what you need:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    # 2. Show text message from agent (skip if products will be shown — cards speak for themselves)
    if result.message and not result.products:
        await update.message.reply_text(result.message)
        add_message(user_id, "assistant", result.message)
        try:
            from bot.services.database import add_message as db_add_msg
            await db_add_msg(user_id, "assistant", result.message)
        except Exception:
            pass

    # 3. Show product cards (shopping)
    if result.products:
        await update.message.reply_text(f"🔍 Found {len(result.products)} result(s):")

        # Store search results in history for context
        shown = ", ".join(f"{c['name']} (${c['price']})" for c in result.products)
        add_message(user_id, "assistant", f"Showed {len(result.products)} products: {shown}")

        for card in result.products:
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
                except Exception as e:
                    logger.warning(f"Image send failed for {card.get('name', '?')}: {e}")
            if not sent:
                try:
                    await update.message.reply_text(
                        f"{card['icon']} {card['caption']}",
                        parse_mode="Markdown",
                        reply_markup=card["keyboard"],
                    )
                except Exception as e:
                    # Last resort — send without markdown
                    logger.warning(f"Card text fallback failed: {e}")
                    await update.message.reply_text(
                        f"{card.get('icon', '🛍')} {card.get('name', 'Product')} — ${card.get('price', '?')}",
                        reply_markup=card.get("keyboard"),
                    )

    # 4. Show credit tip (cross-agent enrichment)
    if result.credit_tip:
        await update.message.reply_text(result.credit_tip)

    # 5. Execute tool action (from credit/shopping agent)
    if result.tool_action:
        await _execute_tool(update, user_id, result.tool_action, session)

    # 6. Fallback if nothing was sent
    if not result.message and not result.products and not result.show_menu and not result.tool_action:
        await update.message.reply_text(
            "I'm here to help with shopping and credit! What can I do for you?",
            reply_markup=main_menu_keyboard(),
        )


async def _execute_tool(update: Update, user_id: int, tool: dict, session: dict):
    """Execute a tool action returned by an agent."""
    name = tool["name"]
    args = tool.get("args", {})

    if name == "search_products":
        # Shouldn't get here — shopping agent handles search internally
        pass

    elif name == "show_cart":
        from bot.agents.shopping_agent import get_cart_message
        msg, kb = get_cart_message(user_id)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif name == "apply_for_credit":
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
            ]) if WEBAPP_URL and WEBAPP_URL.startswith("https://") else None,
        )
        if WEBAPP_URL and WEBAPP_URL.startswith("https://"):
            from bot.handlers.callbacks import _poll_login
            asyncio.create_task(_poll_login_from_text(update, user_id))

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

    elif name == "manage_subscriptions":
        try:
            from bot.services.database import get_subscriptions
            subs = await get_subscriptions(user_id)
            if not subs:
                await update.message.reply_text("📦 You don't have any active subscriptions yet.")
                return
            lines = ["📋 *Your Subscriptions*\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"]
            buttons = []
            for s in subs:
                next_d = s.get("next_delivery", "")
                if hasattr(next_d, "strftime"):
                    next_d = next_d.strftime("%b %d, %Y")
                lines.append(
                    f"📦 *{s['product_name']}*\n"
                    f"   🔄 {s['frequency'].title()} · 📅 Next: {next_d}\n"
                )
                sid = s["id"]
                buttons.append([
                    InlineKeyboardButton(f"✏️ Change {s['product_name'][:15]}", callback_data=f"subscribe:modify:{sid}"),
                    InlineKeyboardButton(f"❌ Cancel", callback_data=f"subscribe:cancel:{sid}"),
                ])
            await update.message.reply_text(
                "\n".join(lines), parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception as e:
            logger.error(f"Manage subscriptions failed: {e}")
            await update.message.reply_text("Couldn't load subscriptions. Try again later.")

    elif name == "analyze_spend":
        try:
            from bot.agents.intelligence import analyze_spend_patterns
            from bot.utils.formatters import dynamic_portfolio_optimize_message
            analysis = await analyze_spend_patterns(user_id)
            if analysis.get("top_categories"):
                await update.message.reply_text(
                    dynamic_portfolio_optimize_message(analysis),
                    parse_mode="Markdown",
                    reply_markup=portfolio_keyboard(),
                )
            else:
                await update.message.reply_text(
                    "📊 No order history yet. Make some purchases and I'll analyze your spending patterns!",
                    reply_markup=portfolio_keyboard(),
                )
        except Exception as e:
            logger.error(f"Spend analysis failed: {e}")
            from bot.utils.formatters import portfolio_optimize_message
            await update.message.reply_text(portfolio_optimize_message(), parse_mode="Markdown")

    elif name == "analyze_subscriptions":
        try:
            from bot.agents.intelligence import detect_subscription_candidates
            from bot.utils.formatters import subscription_candidates_message
            candidates = await detect_subscription_candidates(user_id)
            msg = subscription_candidates_message(candidates)
            buttons = []
            for c in candidates[:3]:
                buttons.append([InlineKeyboardButton(
                    f"✅ Subscribe {c['product_name'][:20]} ({c['suggested_frequency']})",
                    callback_data=f"subscribe:setup:{c['product_id']}:{c['suggested_frequency']}"
                )])
            kb = InlineKeyboardMarkup(buttons) if buttons else None
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.error(f"Subscription analysis failed: {e}")
            await update.message.reply_text("Couldn't analyze subscriptions right now. Try again later.")


async def _poll_login_from_text(update: Update, user_id: int):
    """Background poll for login completion — triggered from free-text credit flow."""
    import httpx

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
                        f"📧 {data['email']}",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(1)
                    await update.message.reply_text(
                        "🔍 *Analyzing your profile...*\n\n_This will only take a moment..._",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(2.5)
                    from bot.services.session import set_state
                    set_state(user_id, FlowState.OFFERS_SHOWN)
                    await update.message.reply_text(
                        f"🎯 We found *3 personalised offers* for you.\nTap one to learn more:\n\n" + all_offers_message(),
                        parse_mode="Markdown",
                        reply_markup=__import__('bot.utils.keyboards', fromlist=['offers_keyboard']).offers_keyboard(),
                    )
                    return
        except Exception:
            pass
