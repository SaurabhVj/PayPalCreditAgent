"""Proactive offer detection — monitors transactions and sends Telegram messages."""

import json
import os
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = "data"
TXNS_FILE = os.path.join(DATA_DIR, "transactions.json")

# Proactive offer templates — mapped to real PayPal/Venmo products
OFFERS = {
    "travel": {
        "emoji": "✈️",
        "message": (
            "Hi! 👋 I noticed you just made a travel booking — exciting trip coming up!\n\n"
            "Did you know the *Venmo Visa Signature Card* automatically gives you "
            "*3% cashback on your top spending category*? With your travel spend, "
            "that's your top category — earning you 3% back automatically.\n\n"
            "Want me to show you the details?"
        ),
        "product": "Venmo Visa Signature Credit Card",
        "highlight": "3% auto cashback on top category · $0 annual fee",
    },
    "dining": {
        "emoji": "🍽",
        "message": (
            "Hi! 👋 I see you love dining out — great taste! 🍔\n\n"
            "The *Venmo Visa Signature Card* automatically detects your top spending category "
            "and gives you *3% cashback*. With your dining spend, that means "
            "*3% back on every meal, delivery, and coffee run* — automatically.\n\n"
            "Want me to show you the details?"
        ),
        "product": "Venmo Visa Signature Credit Card",
        "highlight": "3% auto cashback on dining · $0 annual fee",
    },
    "groceries": {
        "emoji": "🛒",
        "message": (
            "Hi! 👋 I noticed you're stocking up on groceries! 🛒\n\n"
            "Did you know the *PayPal Debit Mastercard* lets you choose a category "
            "each month to earn *5% cashback*? Select groceries as your monthly category "
            "and earn 5% back on every grocery run — up to $1,000/month in spend.\n\n"
            "Want me to show you how it works?"
        ),
        "product": "PayPal Debit Mastercard",
        "highlight": "5% cashback on chosen category each month · No credit check",
    },
    "electronics": {
        "emoji": "📱",
        "message": (
            "Hi! 👋 I noticed you're shopping for electronics — nice pick! 📱\n\n"
            "Big purchases like this are perfect for the *PayPal Credit Card* — "
            "you get *0% APR for 6 months* on purchases of $149 or more. "
            "That means you can spread the cost interest-free.\n\n"
            "Want me to show you the details?"
        ),
        "product": "PayPal Credit Card",
        "highlight": "0% APR for 6 months on $149+ · $0 annual fee",
    },
    "baby": {
        "emoji": "👶",
        "message": (
            "Hi! 👋 It looks like you're shopping for the family! 🍼\n\n"
            "The *PayPal Cashback Mastercard* earns you *3% cashback* on every "
            "purchase made through PayPal checkout — including baby essentials, "
            "diapers, and childcare supplies. Plus *1.5% back everywhere else*.\n\n"
            "Want to see if you're eligible?"
        ),
        "product": "PayPal Cashback Mastercard",
        "highlight": "3% on PayPal purchases · 1.5% everywhere else · $0 fee",
    },
    "school": {
        "emoji": "🎒",
        "message": (
            "Hi! 👋 I noticed you're shopping for school essentials! 📚\n\n"
            "Did you know *Venmo offers a Teen Account* for ages 13-17? "
            "Your child gets their own supervised debit card with spending limits "
            "and you can monitor every transaction from your Venmo app.\n\n"
            "Want me to show you how it works?"
        ),
        "product": "Venmo Teen Account",
        "highlight": "Supervised debit card · Parental controls · Ages 13-17",
    },
}


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_transactions() -> dict:
    _ensure_dir()
    if os.path.exists(TXNS_FILE):
        with open(TXNS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_transactions(data: dict):
    _ensure_dir()
    with open(TXNS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_transaction(username: str, merchant: str, category: str, amount: float, icon: str = "💳") -> dict:
    """Add a transaction and return detection result."""
    data = load_transactions()
    if username not in data:
        data[username] = {"transactions": [], "processed_count": 0}

    txn = {
        "merchant": merchant,
        "category": category,
        "amount": amount,
        "icon": icon,
        "timestamp": datetime.now().isoformat(),
        "processed": False,
    }
    data[username]["transactions"].append(txn)
    save_transactions(data)

    # Check if this triggers a proactive offer
    triggered = detect_pattern(category)
    return {"status": "ok", "proactive_triggered": triggered is not None, "pattern": triggered}


TRIGGER_CATEGORIES = {"travel", "dining", "groceries", "electronics", "baby", "school"}
NON_TRIGGER_CATEGORIES = {"fashion", "entertainment"}


def detect_pattern(category: str) -> str | None:
    """Detect which proactive offer to trigger based on category."""
    if category in TRIGGER_CATEGORIES:
        return category
    return None


def get_unprocessed_triggers(username: str) -> list[dict]:
    """Get unprocessed transactions that should trigger proactive offers."""
    data = load_transactions()
    user_data = data.get(username, {})
    txns = user_data.get("transactions", [])

    triggers = []
    for i, txn in enumerate(txns):
        if txn.get("processed"):
            continue
        pattern = detect_pattern(txn["category"])
        if pattern:
            triggers.append({
                "index": i,
                "pattern": pattern,
                "merchant": txn["merchant"],
                "amount": txn["amount"],
                "offer": OFFERS[pattern],
            })

    return triggers


def mark_processed(username: str, txn_index: int):
    """Mark a transaction as processed so we don't trigger again."""
    data = load_transactions()
    if username in data and txn_index < len(data[username]["transactions"]):
        data[username]["transactions"][txn_index]["processed"] = True
        save_transactions(data)


async def proactive_loop(bot):
    """Background loop — checks for new transactions and sends proactive messages."""
    from bot.services.user_store import get_all_users
    from bot.utils.keyboards import proactive_keyboard

    logger.info("Proactive detection engine started")

    while True:
        await asyncio.sleep(15)  # Check every 15 seconds

        try:
            users = get_all_users()  # {username: chat_id}

            # Handle broadcast transactions (from e-commerce checkout)
            broadcast_triggers = get_unprocessed_triggers("__broadcast__")
            for trigger in broadcast_triggers:
                offer = trigger["offer"]
                msg = offer["message"]

                # Send to ALL registered users
                for username, chat_id in users.items():
                    try:
                        from bot.services.session import set_proactive_context
                        set_proactive_context(chat_id, {
                            "merchant": trigger["merchant"],
                            "amount": trigger["amount"],
                            "category": trigger["pattern"],
                            "product": offer["product"],
                        })

                        await bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode="Markdown",
                            reply_markup=proactive_keyboard(trigger["pattern"]),
                        )
                        logger.info(f"Broadcast proactive offer sent to @{username} (pattern: {trigger['pattern']})")
                    except Exception as e:
                        logger.error(f"Failed to send broadcast to @{username}: {e}")

                mark_processed("__broadcast__", trigger["index"])

            # Handle per-user transactions (from transaction simulator)
            for username, chat_id in users.items():
                triggers = get_unprocessed_triggers(username)

                for trigger in triggers:
                    offer = trigger["offer"]
                    msg = offer["message"]

                    try:
                        from bot.services.session import set_proactive_context
                        set_proactive_context(chat_id, {
                            "merchant": trigger["merchant"],
                            "amount": trigger["amount"],
                            "category": trigger["pattern"],
                            "product": offer["product"],
                        })

                        await bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode="Markdown",
                            reply_markup=proactive_keyboard(trigger["pattern"]),
                        )
                        mark_processed(username, trigger["index"])
                        logger.info(f"Proactive offer sent to @{username} (pattern: {trigger['pattern']})")
                    except Exception as e:
                        logger.error(f"Failed to send proactive message to @{username}: {e}")

        except Exception as e:
            logger.debug(f"Proactive loop error: {e}")
