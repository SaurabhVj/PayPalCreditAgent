"""Inline button callback handler."""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
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
        await _handle_credit_flow(query, user_id)

    elif data == "topic:balance":
        await query.message.reply_text(
            balance_message(), parse_mode="Markdown",
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

    # ── Offer selection ──
    elif data.startswith("offer:"):
        index = int(data.split(":")[1])
        set_selected_offer(user_id, index)
        set_state(user_id, FlowState.SELECTED)
        await query.message.reply_text(
            confirm_message(index),
            parse_mode="Markdown",
            reply_markup=confirm_keyboard(),
        )

    # ── Actions ──
    elif data == "action:submit":
        await _handle_submit(query, user_id)

    elif data == "action:back_offers":
        set_state(user_id, FlowState.OFFERS_SHOWN)
        await query.message.reply_text(
            all_offers_message(),
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
        )

    # ── Support ──
    elif data.startswith("support:"):
        await _handle_support(query, data.split(":")[1])


async def _handle_credit_flow(query, user_id: int):
    """Start the credit application flow."""
    # Step: Scoring
    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text(
        scoring_message(),
        parse_mode="Markdown",
    )

    # Simulate NBA model processing
    await asyncio.sleep(2)

    set_state(user_id, FlowState.OFFERS_SHOWN)
    await query.message.reply_text(
        all_offers_message(),
        parse_mode="Markdown",
        reply_markup=offers_keyboard(),
    )


async def _handle_submit(query, user_id: int):
    """Process application submission."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        await query.message.reply_text("Please select an offer first.")
        return

    # Simulate processing
    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text("⏳ _Processing your application..._", parse_mode="Markdown")
    await asyncio.sleep(2)

    set_state(user_id, FlowState.APPROVED)
    await query.message.reply_text(
        approval_message(offer_idx),
        parse_mode="Markdown",
        reply_markup=post_approval_keyboard(),
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


def _card_manage_message() -> str:
    return (
        "🃏 *Card Management*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "Card: •••• •••• •••• 4821\n"
        "Holder: ARUN SHARMA\n"
        "Expiry: 09/28\n"
        "Type: PayPal Pay Later\n\n"
        "*Controls:*\n"
        "🌐 Online Purchases: ✅ On\n"
        "✈️ International: ❌ Off\n"
        "📱 Contactless: ✅ On\n"
        "🔔 Spend Alerts: ✅ On\n\n"
        "*Quick Actions:*\n"
        "🧊 Freeze | 🔄 Replace | ⚠️ Report | 🔑 PIN"
    )
