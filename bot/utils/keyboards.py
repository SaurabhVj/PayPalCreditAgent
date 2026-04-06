"""Inline keyboard builders for Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from bot.models.offers import CREDIT_OFFERS
from bot.config import WEBAPP_URL


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """2x2 topic menu grid matching v9 prototype."""
    buttons = [
        [
            InlineKeyboardButton("💳 Apply for Credit", callback_data="topic:credit"),
            InlineKeyboardButton("💰 Check Balance", callback_data="topic:balance"),
        ],
        [
            InlineKeyboardButton("🎁 View Rewards", callback_data="topic:rewards"),
            InlineKeyboardButton("🙋 Support", callback_data="topic:support"),
        ],
    ]
    # Add Mini App button if WEBAPP_URL is set and uses HTTPS
    if WEBAPP_URL and WEBAPP_URL.startswith("https://"):
        buttons.append([
            InlineKeyboardButton("📱 Open Full App", web_app=WebAppInfo(url=WEBAPP_URL + "/webapp")),
        ])
    return InlineKeyboardMarkup(buttons)


def post_approval_keyboard() -> InlineKeyboardMarkup:
    """Post-approval menu — matches v9 post-done topic grid."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 View Statement", callback_data="action:statement"),
            InlineKeyboardButton("🃏 Manage Card", callback_data="action:card"),
        ],
        [
            InlineKeyboardButton("💰 Check Balance", callback_data="topic:balance"),
            InlineKeyboardButton("🎁 View Rewards", callback_data="topic:rewards"),
        ],
    ])


def offers_keyboard() -> InlineKeyboardMarkup:
    """3 credit offer buttons."""
    buttons = []
    for i, offer in enumerate(CREDIT_OFFERS):
        label = f"{'⭐ ' if offer['highlight'] else ''}{offer['name']} — {offer['amount']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"offer:{i}")])
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirm or go back."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Submit Application", callback_data="action:submit")],
        [InlineKeyboardButton("← Back to Offers", callback_data="action:back_offers")],
    ])


def yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes", callback_data=f"{prefix}:yes"),
            InlineKeyboardButton("No", callback_data=f"{prefix}:no"),
        ],
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Call PayPal", callback_data="support:call")],
        [InlineKeyboardButton("💬 Live Chat", callback_data="support:chat")],
        [InlineKeyboardButton("⚠️ Dispute a Charge", callback_data="support:dispute")],
        [InlineKeyboardButton("🔒 Lost Card", callback_data="support:lost")],
    ])
