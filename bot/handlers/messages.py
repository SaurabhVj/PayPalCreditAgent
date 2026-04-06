"""Free-text message handler — routes to appropriate response."""

import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot.utils.keyboards import main_menu_keyboard, offers_keyboard
from bot.utils.formatters import (
    balance_message, statement_message, rewards_message,
    all_offers_message, welcome_message,
)
from bot.services.session import get_state, set_state
from bot.models.state import FlowState


# Intent patterns from v9 prototype — ORDER MATTERS (specific before general)
INTENTS = [
    ("card_manage", r"manage|card settings|card details|controls|settings|freeze|block|lock|suspend|replace|lost card"),
    ("score", r"credit score|fico|creditworthiness|credit rating"),
    ("credit", r"apply|credit card|loan|borrow|offer|limit increase|get credit|pay later|cashback master|credit line"),
    ("balance", r"balance|owe|due date|minimum|available credit|statement summary"),
    ("statement", r"statement|transactions|spending|history|recent|charges|purchases"),
    ("rewards", r"reward|cashback|points|miles|earn|redeem|upgrade"),
    ("limit", r"limit|how much left|remaining|budget|utilis|utiliz"),
    ("pay", r"pay|make payment"),
    ("support", r"support|contact|help|issue|problem|talk human|agent|representative|dispute|call paypal"),
    ("menu", r"^hi$|^hello$|what can|commands|options|menu|start|home"),
    ("thanks", r"thanks|thank you|thx|great|awesome|perfect|nice|got it|^ok$|^okay$"),
]


def detect_intent(text: str) -> str | None:
    text_lower = text.lower().strip()
    for intent, pattern in INTENTS:
        if re.search(pattern, text_lower):
            return intent
    return None


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    user_id = update.effective_user.id
    intent = detect_intent(text)

    await update.message.chat.send_action(ChatAction.TYPING)

    if intent == "credit":
        set_state(user_id, FlowState.OFFERS_SHOWN)
        await update.message.reply_text(
            all_offers_message(),
            parse_mode="Markdown",
            reply_markup=offers_keyboard(),
        )

    elif intent in ("balance", "limit"):
        await update.message.reply_text(
            balance_message(), parse_mode="Markdown",
        )

    elif intent == "statement":
        await update.message.reply_text(
            statement_message(), parse_mode="Markdown",
        )

    elif intent == "rewards":
        await update.message.reply_text(
            rewards_message(), parse_mode="Markdown",
        )

    elif intent == "card_manage":
        from bot.services.session import get_session
        name = get_session(user_id).get("name", "User")
        await update.message.reply_text(
            "🃏 *Card Management*\n"
            "━━━━━━━━━━━━━━━━━\n"
            "Card: •••• •••• •••• 4821\n"
            f"Holder: {name.upper()}\n"
            "Expiry: 09/28\n\n"
            "*Controls:*\n"
            "🌐 Online: ✅ | ✈️ Intl: ❌ | 📱 Tap: ✅ | 🔔 Alerts: ✅",
            parse_mode="Markdown",
        )

    elif intent == "score":
        await update.message.reply_text(
            "📊 *Credit Score*\n━━━━━━━━━━━━━━━━━\n"
            "FICO Score: *742*\n"
            "Rating: _Excellent_\n"
            "Last updated: Apr 1, 2026",
            parse_mode="Markdown",
        )

    elif intent == "pay":
        await update.message.reply_text(
            "💳 *Make a Payment*\n\n"
            "Current balance: *$847.23*\n"
            "Min payment: $25.00\n"
            "Due: Apr 15\n\n"
            "_Payment feature coming soon._",
            parse_mode="Markdown",
        )

    elif intent == "support":
        from bot.utils.keyboards import support_keyboard
        await update.message.reply_text(
            "🙋 *How can we help?*", parse_mode="Markdown",
            reply_markup=support_keyboard(),
        )

    elif intent == "menu":
        await update.message.reply_text(
            welcome_message(), parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif intent == "thanks":
        await update.message.reply_text(
            "You're welcome! 😊 Type /menu if you need anything else."
        )

    else:
        # No intent matched — try LLM
        from bot.services.llm_service import ask_llm
        llm_response = await ask_llm(text)
        if llm_response:
            await update.message.reply_text(llm_response)
        else:
            await update.message.reply_text(
                "I'm not sure I understand. Here's what I can help with:",
                reply_markup=main_menu_keyboard(),
            )
