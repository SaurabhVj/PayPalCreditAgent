"""Inline button callback handler — full v9 flow with dummy login."""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot.config import WEBAPP_URL
from bot.services.session import (
    get_state, set_state, set_selected_offer, get_selected_offer,
)
from bot.models.state import FlowState
from bot.models.offers import CREDIT_OFFERS
from bot.utils.keyboards import (
    offers_keyboard, confirm_keyboard, post_approval_keyboard,
    main_menu_keyboard, support_keyboard,
)
from bot.utils.formatters import (
    all_offers_message, confirm_message, approval_message,
    balance_message, statement_message, rewards_message,
    scoring_message,
)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # ── Topic selections ──
    if data == "topic:credit":
        await _handle_credit_start(query, user_id)

    elif data == "topic:balance":
        await query.message.reply_text(
            balance_message(), parse_mode="Markdown",
            reply_markup=_post_balance_keyboard(),
        )

    elif data == "topic:rewards":
        await query.message.reply_text(
            rewards_message(), parse_mode="Markdown",
        )

    elif data == "topic:support":
        await query.message.reply_text(
            "🙋 *How can we help?*\n\nChoose a support option:",
            parse_mode="Markdown",
            reply_markup=support_keyboard(),
        )

    # ── Auth flow — after Mini App login completes ──
    elif data == "auth:connected":
        await _handle_post_login(query, user_id)

    # ── Offer selection ──
    elif data.startswith("offer:"):
        index = int(data.split(":")[1])
        set_selected_offer(user_id, index)
        set_state(user_id, FlowState.SELECTED)

        o = CREDIT_OFFERS[index]
        await query.message.reply_text(
            f"*{o['name']}*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💳 Credit Limit: *{o['amount']}*\n"
            f"📋 {o['detail']}\n"
            f"📊 Match Score: *{o['score']}%*\n"
            f"🏷 _{o['tag']}_\n\n"
            f"Would you like to go ahead?",
            parse_mode="Markdown",
            reply_markup=_offer_action_keyboard(),
        )

    # ── Offer actions ──
    elif data == "action:apply_now":
        await _handle_confirm(query, user_id)

    elif data == "action:tell_more":
        await _handle_tell_more(query, user_id)

    elif data == "action:submit":
        await _handle_submit(query, user_id)

    elif data == "action:back_offers":
        set_state(user_id, FlowState.OFFERS_SHOWN)
        await query.message.reply_text(
            "Of course! Here are all three options again:\n\n" + all_offers_message(),
            parse_mode="Markdown",
            reply_markup=offers_keyboard(),
        )

    elif data == "action:statement":
        await query.message.reply_text(
            statement_message(), parse_mode="Markdown",
        )

    elif data == "action:card":
        await query.message.reply_text(
            _card_manage_message(), parse_mode="Markdown",
            reply_markup=_card_action_keyboard(),
        )

    # ── Card actions ──
    elif data.startswith("card:"):
        await _handle_card_action(query, data.split(":")[1])

    # ── Support ──
    elif data.startswith("support:"):
        await _handle_support(query, data.split(":")[1])


# ── STEP 1: Show auth card ──
async def _handle_credit_start(query, user_id: int):
    """Show the Connect PayPal auth card."""
    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)

    await query.message.reply_text(
        "Great choice! Our NBA Model will match you to the best credit "
        "product based on your PayPal profile.\n\n"
        "First, let me securely connect your PayPal account. "
        "This uses OAuth — I never see your password. 🔒",
        parse_mode="Markdown",
    )

    await asyncio.sleep(0.5)

    # Auth card — "Connect with PayPal" opens Mini App login screen
    login_url = f"{WEBAPP_URL}/webapp#login"
    await query.message.reply_text(
        "🔐 *Connect PayPal*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "Sign in to unlock personalised credit offers.\n\n"
        "👤 *Arun Sharma*\n"
        "📧 arun.sharma@email.com\n",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Connect with PayPal", web_app=WebAppInfo(url=login_url))],
        ]),
    )


# ── STEP 2: Post Mini App login — continues flow in bot chat ──
async def _handle_post_login(query, user_id: int):
    """Called after user logs in via Mini App and taps 'Continue in chat'."""
    await query.message.reply_text(
        "✅ *Connected successfully!*\n\n"
        "👤 Arun Sharma\n"
        "📧 arun.sharma@email.com\n"
        "🏦 PayPal member: 36 months\n"
        "💳 Credit band: _prime_",
        parse_mode="Markdown",
    )
    await asyncio.sleep(1)
    await _handle_scoring(query, user_id)


# ── STEP 3: NBA Scoring ──
async def _handle_scoring(query, user_id: int):
    """Run NBA model scoring."""
    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text(
        scoring_message(),
        parse_mode="Markdown",
    )

    await asyncio.sleep(2.5)

    await query.message.reply_text(
        "✅ *NBA Model complete!*\n"
        "📊 Offers matched: *3*\n"
        "⏱ Decision time: *2.8 seconds*\n"
        "🧠 Model: _nba-credit-v4.1_",
        parse_mode="Markdown",
    )
    await asyncio.sleep(1)

    # Step 5: Show offers
    set_state(user_id, FlowState.OFFERS_SHOWN)
    await query.message.reply_text(
        "🎯 Great news — the NBA Model matched you to *3 personalised offers*.\n"
        "Tap one to learn more:\n\n" + all_offers_message(),
        parse_mode="Markdown",
        reply_markup=offers_keyboard(),
    )


# ── STEP 4: Confirm application ──
async def _handle_confirm(query, user_id: int):
    """Show application confirmation card."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        await query.message.reply_text("Please select an offer first.")
        return

    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(0.8)

    await query.message.reply_text(
        "✨ Here's your application summary. Review and tap Submit:\n\n" +
        confirm_message(offer_idx),
        parse_mode="Markdown",
        reply_markup=confirm_keyboard(),
    )
    set_state(user_id, FlowState.CONFIRMED)


# ── STEP 5: Submit + Approve ──
async def _handle_submit(query, user_id: int):
    """Process application submission."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        await query.message.reply_text("Please select an offer first.")
        return

    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text("⏳ _Processing your application..._", parse_mode="Markdown")
    await asyncio.sleep(2.5)

    o = CREDIT_OFFERS[offer_idx]
    set_state(user_id, FlowState.APPROVED)

    await query.message.reply_text(
        f"🎊 *Approved, Arun Sharma!*\n\n"
        f"Your *{o['name']}* is active.\n\n"
        f"💳 Credit Limit: *{o['amount']}*\n"
        f"⏱ Decision Time: *3.1 seconds*\n"
        f"📋 Status: _Active_\n\n"
        f"📲 All done inside Telegram — no app downloads, no redirects. "
        f"That's Agentic Commerce.\n\n"
        f"What would you like to do next?",
        parse_mode="Markdown",
        reply_markup=post_approval_keyboard(),
    )


async def _handle_tell_more(query, user_id: int):
    """Show more details about the selected offer."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        return
    o = CREDIT_OFFERS[offer_idx]

    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)

    await query.message.reply_text(
        f"Here's what to know about *{o['name']}*:\n\n"
        f"✅ *Instant decision* — know in under 4 seconds\n"
        f"🔒 *No hard credit pull* to check eligibility\n"
        f"📱 *Digital-first* — manage entirely in PayPal\n"
        f"🛡 *Buyer Protection* included on all purchases\n"
        f"💸 *{o['detail']}*\n\n"
        f"Ready to proceed?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, apply now", callback_data="action:apply_now")],
            [InlineKeyboardButton("← See other offers", callback_data="action:back_offers")],
        ]),
    )


async def _handle_card_action(query, action: str):
    msgs = {
        "freeze": "🧊 *Card Frozen*\n\nYour card has been temporarily frozen. No transactions will be processed.\n\nTap /menu to unfreeze or manage your card.",
        "replace": "🔄 *Replacement Requested*\n\nA new card will arrive in 3-5 business days.\nYour current card remains active until the new one is activated.",
        "report": "⚠️ *Report Filed*\n\nWe've flagged your card for review. Our fraud team will contact you within 24 hours.",
        "pin": "🔑 *PIN Change*\n\nA PIN change link has been sent to arun.sharma@email.com.\nThe link expires in 15 minutes.",
    }
    await query.message.reply_text(
        msgs.get(action, "Action completed."),
        parse_mode="Markdown",
    )


async def _handle_support(query, action: str):
    messages = {
        "call": "📞 *Call PayPal*\n\n1-888-221-1161\nMon–Fri 6am–6pm PT",
        "chat": "💬 *Live Chat*\n\nVisit: paypal.com/us/smarthelp/home",
        "dispute": "⚠️ *Dispute a Charge*\n\n1. Go to Activity\n2. Find the transaction\n3. Tap 'Report a Problem'",
        "lost": "🔒 *Lost Card*\n\nYour card has been frozen for safety.\nA replacement will arrive in 3-5 business days.",
    }
    await query.message.reply_text(
        messages.get(action, "Contact support at 1-888-221-1161"),
        parse_mode="Markdown",
    )


def _offer_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, apply now", callback_data="action:apply_now")],
        [InlineKeyboardButton("ℹ️ Tell me more", callback_data="action:tell_more")],
        [InlineKeyboardButton("← See other offers", callback_data="action:back_offers")],
    ])


def _post_balance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 View Statement", callback_data="action:statement")],
        [InlineKeyboardButton("🃏 Manage Card", callback_data="action:card")],
    ])


def _card_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧊 Freeze", callback_data="card:freeze"),
            InlineKeyboardButton("🔄 Replace", callback_data="card:replace"),
        ],
        [
            InlineKeyboardButton("⚠️ Report", callback_data="card:report"),
            InlineKeyboardButton("🔑 PIN", callback_data="card:pin"),
        ],
    ])


def _card_manage_message() -> str:
    return (
        "🃏 *Card Management*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "💳 *Virtual Card*\n"
        "Card: `•••• •••• •••• 4821`\n"
        "Holder: ARUN SHARMA\n"
        "Expiry: 09/28\n"
        "Type: PayPal Pay Later\n\n"
        "📊 *Spending Limit*\n"
        "Used: $847.23 of $2,500 (33.9%)\n"
        "▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░ 33.9%\n\n"
        "*Controls:*\n"
        "🌐 Online Purchases: ✅ On\n"
        "✈️ International: ❌ Off\n"
        "📱 Contactless: ✅ On\n"
        "🔔 Spend Alerts: ✅ On"
    )
