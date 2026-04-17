"""PayPal credit card catalog — all cards across PayPal + Venmo ecosystem."""

PAYPAL_CARDS = [
    {
        "id": "cashback_mc",
        "name": "PayPal Cashback Mastercard",
        "type": "credit",
        "issuer": "Synchrony Bank",
        "rewards": {
            "paypal_purchases": "3% cashback",
            "everything_else": "1.5% cashback",
        },
        "annual_fee": "$0",
        "apr": "Variable (20.99% - 29.99%)",
        "special": "No rotating categories, unlimited cashback",
        "best_for": ["online shopping", "paypal checkout", "general spending"],
        "default_assigned": True,
        "default_balance": 3240,
        "default_limit": 22000,
        "default_rewards_earned": 114.20,
    },
    {
        "id": "everyday_cash",
        "name": "PayPal Everyday Cash",
        "type": "credit",
        "issuer": "Synchrony Bank",
        "rewards": {
            "all_categories": "2% cashback flat",
        },
        "annual_fee": "$0",
        "apr": "Variable",
        "special": "Simple flat-rate card, no category tracking",
        "best_for": ["groceries", "gas", "general spending", "simplicity"],
        "default_assigned": True,
        "default_balance": 580,
        "default_limit": 20000,
        "default_rewards_earned": 286,
    },
    {
        "id": "paypal_credit",
        "name": "PayPal Credit Card",
        "type": "credit",
        "issuer": "Synchrony Bank",
        "rewards": {
            "special_financing": "0% APR for 6 months on purchases $149+",
        },
        "annual_fee": "$0",
        "apr": "Variable (after promo period)",
        "special": "Best for big-ticket purchases, interest-free financing",
        "best_for": ["electronics", "big purchases", "financing", "appliances"],
        "default_assigned": False,
    },
    {
        "id": "venmo_visa",
        "name": "Venmo Visa Signature",
        "type": "credit",
        "issuer": "Synchrony Bank",
        "rewards": {
            "top_category": "3% cashback (auto-detected)",
            "second_category": "2% cashback",
            "everything_else": "1% cashback",
        },
        "annual_fee": "$0",
        "apr": "Variable",
        "categories": ["travel", "dining", "groceries", "entertainment", "bills"],
        "special": "Auto-detects your top spending category each month",
        "best_for": ["travel", "dining", "groceries", "category spenders"],
        "default_assigned": False,
    },
    {
        "id": "debit_mc",
        "name": "PayPal Debit Mastercard",
        "type": "debit",
        "rewards": {
            "chosen_category": "5% cashback on 1 category you pick monthly",
        },
        "chooseable_categories": ["fuel", "groceries", "restaurants", "apparel"],
        "annual_fee": "$0",
        "special": "No credit check, choose your 5% category monthly, up to $1000/month spend",
        "best_for": ["budget conscious", "no credit check", "category maximizers"],
        "default_assigned": False,
    },
    {
        "id": "venmo_teen",
        "name": "Venmo Teen Account",
        "type": "debit",
        "rewards": {},
        "features": ["parental controls", "spending limits", "transaction visibility", "supervised debit card"],
        "annual_fee": "$0",
        "special": "Ages 13-17, parent sets up and monitors",
        "best_for": ["teens 13-17", "parents", "first card"],
        "default_assigned": False,
    },
]

# Cards assigned to new users by default
DEFAULT_PORTFOLIO = [c for c in PAYPAL_CARDS if c.get("default_assigned")]

# Cards available to recommend/apply for
RECOMMENDABLE_CARDS = [c for c in PAYPAL_CARDS if not c.get("default_assigned")]


def get_card_by_id(card_id: str) -> dict | None:
    for c in PAYPAL_CARDS:
        if c["id"] == card_id:
            return c
    return None


def get_card_by_name(name: str) -> dict | None:
    """Look up card by display name (case-insensitive partial match)."""
    name_lower = name.lower()
    for c in PAYPAL_CARDS:
        if c["name"].lower() == name_lower or name_lower in c["name"].lower():
            return c
    return None


def get_best_card_for_category(category: str, user_cards: list[dict] | None = None) -> dict | None:
    """Given a purchase category, which card earns the most?"""
    category_map = {
        "travel": ("venmo_visa", "3% auto top category"),
        "dining": ("venmo_visa", "3% auto top category"),
        "groceries": ("debit_mc", "5% chosen category"),
        "electronics": ("paypal_credit", "0% APR 6 months on $149+"),
        "baby": ("cashback_mc", "3% via PayPal checkout"),
        "school": ("venmo_teen", "Supervised teen debit"),
        "fashion": ("everyday_cash", "2% flat on everything"),
        "entertainment": ("venmo_visa", "3% auto top category"),
        "home": ("paypal_credit", "0% APR 6 months on $149+"),
    }
    result = category_map.get(category)
    if result:
        card = get_card_by_id(result[0])
        if card:
            return {**card, "reason": result[1]}
    return None
