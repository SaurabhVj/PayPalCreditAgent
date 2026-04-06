"""Command handlers: /start, /menu, /help, /reset."""

from telegram import Update
from telegram.ext import ContextTypes
from bot.utils.keyboards import main_menu_keyboard
from bot.services.session import reset_session, set_state, get_session
from bot.models.state import FlowState


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_session(user.id)
    set_state(user.id, FlowState.GREETED)

    # Store Telegram user's name as default (overridden after PayPal login)
    session = get_session(user.id)
    session["name"] = user.first_name or "there"
    session["email"] = ""

    name = user.first_name or "there"
    await update.message.reply_text(
        f"👋 *Welcome to PayPal Credit Agent*\n\n"
        f"Hi {name}! I can help you with credit products, "
        f"check your balance, view rewards, and more.\n\n"
        f"Choose an option below or just type your question:",
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
        "*PayPal Credit Agent — Help*\n\n"
        "💳 /start — Start fresh\n"
        "📋 /menu — Show main menu\n"
        "↺ /reset — Reset session\n"
        "❓ /help — This message\n\n"
        "You can also type naturally:\n"
        '• _"I want a credit card"_\n'
        '• _"Show my balance"_\n'
        '• _"View transactions"_\n'
        '• _"What rewards do I have?"_',
        parse_mode="Markdown",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_session(update.effective_user.id)
    await update.message.reply_text(
        "↺ Session reset. Type /start to begin again."
    )
