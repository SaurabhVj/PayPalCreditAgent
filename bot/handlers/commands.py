"""Command handlers: /start, /menu, /help, /reset."""

from telegram import Update
from telegram.ext import ContextTypes
from bot.utils.keyboards import main_menu_keyboard
from bot.services.session import reset_session, set_state, get_session
from bot.services.user_store import store_user, store_user_db
from bot.models.state import FlowState


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_session(user.id)
    set_state(user.id, FlowState.GREETED)

    # Store Telegram user's name as default
    session = get_session(user.id)
    session["name"] = user.first_name or "there"
    session["email"] = ""

    # Store in cache + JSON
    if user.username:
        store_user(user.username.lower(), user.id)

    # Store in Postgres
    await store_user_db(user.id, user.username or "", user.first_name or "", "")

    name = user.first_name or "there"
    await update.message.reply_text(
        f"👋 *Welcome to PayPal Assistant*\n\n"
        f"Hi {name}! I can help you with *shopping*, *credit cards*, "
        f"*rewards*, and more.\n\n"
        f"Choose an option or just tell me what you need:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Choose an option:",
        reply_markup=main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*PayPal Assistant — Help*\n\n"
        "🛍 Search for any product: _\"Nike Jordan shoes\"_\n"
        "💳 Credit cards: _\"apply for credit\"_\n"
        "💰 Balance: _\"what's my balance\"_\n"
        "🎁 Rewards: _\"show my rewards\"_\n"
        "🛒 Cart: _\"show my cart\"_\n\n"
        "Commands:\n"
        "/start — Start fresh\n"
        "/menu — Show menu\n"
        "/reset — Reset session\n"
        "/help — This message",
        parse_mode="Markdown",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_session(update.effective_user.id)
    await update.message.reply_text(
        "↺ Session reset. Type /start to begin again."
    )
