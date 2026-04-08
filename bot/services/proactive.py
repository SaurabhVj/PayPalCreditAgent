"""Proactive offer detection — monitors transactions and sends Telegram messages."""

import json
import os
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = "data"
TXNS_FILE = os.path.join(DATA_DIR, "transactions.json")

# Merchant → category patterns for proactive offers
TRAVEL_KEYWORDS = ["airline", "emirates", "singapore air", "booking.com", "marriott", "hotel", "flight", "airport"]
BABY_KEYWORDS = ["firstcry", "mothercare", "babycenter", "paediatric", "pediatric", "dr. mehta", "childcare"]
DINING_KEYWORDS = ["uber eats", "doordash", "starbucks", "restaurant", "cafe", "zomato", "swiggy"]

# Proactive offer templates
OFFERS = {
    "travel": {
        "emoji": "✈️",
        "message": (
            "Hi! 👋 I noticed you just made a travel booking — exciting trip coming up!\n\n"
            "Quick thought: You could be earning *free lounge access + 3x miles* on that purchase "
            "with the right credit card.\n\n"
            "Want me to show you a 60-second option?"
        ),
        "product": "PayPal Miles+",
        "highlight": "75,000 sign-up miles + Priority Pass lounge access",
    },
    "baby": {
        "emoji": "👶",
        "message": (
            "Hi! 👋 Congratulations — it looks like your family is growing! 🍼\n\n"
            "I noticed some family-related purchases, and I wanted to share a card "
            "designed specifically for young families — with *5% cashback on childcare* "
            "and *3% on groceries*.\n\n"
            "Want to see if you're pre-approved?"
        ),
        "product": "PayPal Family Rewards",
        "highlight": "5% childcare cashback + 3% groceries",
    },
    "dining": {
        "emoji": "🍽",
        "message": (
            "Hi! 👋 I see you love dining out — great taste! 🍔\n\n"
            "Did you know you could earn *3% cashback on all dining* with the right card? "
            "Based on your spending, that's about *$84/year back in your pocket*.\n\n"
            "Want me to show you the details?"
        ),
        "product": "PayPal Cashback Mastercard",
        "highlight": "3% dining cashback + 2% everywhere else",
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


def detect_pattern(category: str) -> str | None:
    """Detect which proactive offer to trigger based on category."""
    if category == "travel":
        return "travel"
    elif category == "baby":
        return "baby"
    elif category == "dining":
        return "dining"
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
            txn_data = load_transactions()

            for username, chat_id in users.items():
                triggers = get_unprocessed_triggers(username)

                for trigger in triggers:
                    offer = trigger["offer"]
                    merchant = trigger["merchant"]
                    amount = trigger["amount"]

                    msg = offer["message"]

                    try:
                        # Store proactive context in user's session for follow-up questions
                        from bot.services.session import set_proactive_context
                        from bot.services.user_store import get_chat_id
                        set_proactive_context(chat_id, {
                            "merchant": merchant,
                            "amount": amount,
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
