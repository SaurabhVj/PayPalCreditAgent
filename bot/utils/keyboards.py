"""Inline keyboard builders for Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from bot.models.offers import CREDIT_OFFERS
from bot.config import WEBAPP_URL


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu with shopping + credit options."""
    buttons = [
        [InlineKeyboardButton("🛍 Shop Products", callback_data="topic:shop")],
        [
            InlineKeyboardButton("💳 Credit Cards", callback_data="topic:credit_menu"),
            InlineKeyboardButton("🛒 My Cart", callback_data="topic:cart"),
        ],
    ]
    if WEBAPP_URL and WEBAPP_URL.startswith("https://"):
        buttons.append([
            InlineKeyboardButton("📱 Open Full App", web_app=WebAppInfo(url=WEBAPP_URL + "/webapp")),
        ])
    return InlineKeyboardMarkup(buttons)


def credit_menu_keyboard() -> InlineKeyboardMarkup:
    """Credit-specific submenu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Apply for Credit", callback_data="topic:credit"),
            InlineKeyboardButton("🎁 View Rewards", callback_data="topic:rewards"),
        ],
        [
            InlineKeyboardButton("📊 Credit Portfolio", callback_data="topic:portfolio"),
            InlineKeyboardButton("⚖️ Collections", callback_data="topic:collections"),
        ],
        [InlineKeyboardButton("← Back to Menu", callback_data="topic:main_menu")],
    ])


def post_approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 View Statement", callback_data="action:statement"),
            InlineKeyboardButton("🃏 Manage Card", callback_data="action:card"),
        ],
        [
            InlineKeyboardButton("💰 Check Balance", callback_data="topic:balance"),
            InlineKeyboardButton("📊 Credit Portfolio", callback_data="topic:portfolio"),
        ],
    ])


def offers_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for i, offer in enumerate(CREDIT_OFFERS):
        label = f"{'⭐ ' if offer['highlight'] else ''}{offer['name']} — {offer['amount']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"offer:{i}")])
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Submit Application", callback_data="action:submit")],
        [InlineKeyboardButton("← Back to Offers", callback_data="action:back_offers")],
    ])


def portfolio_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Optimize My Spend", callback_data="portfolio:optimize")],
        [InlineKeyboardButton("🔀 Compare Cards", callback_data="portfolio:compare")],
        [InlineKeyboardButton("📈 What-If Analysis", callback_data="portfolio:whatif")],
    ])


def collections_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Show me options", callback_data="collect:options")],
        [InlineKeyboardButton("😔 I can't pay right now", callback_data="collect:hardship")],
        [InlineKeyboardButton("❌ I dispute this balance", callback_data="collect:dispute")],
    ])


def collections_plan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Option A — Minimum today", callback_data="collect:plan_a")],
        [InlineKeyboardButton("Option B — 3-month instalments", callback_data="collect:plan_b")],
        [InlineKeyboardButton("Option C — Lump sum settlement", callback_data="collect:plan_c")],
    ])


def proactive_keyboard(pattern: str = "travel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, show me", callback_data=f"proactive:yes:{pattern}")],
        [InlineKeyboardButton("❌ Not right now", callback_data="proactive:no")],
    ])
