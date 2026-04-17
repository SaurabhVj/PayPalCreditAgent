"""Backend-driven intelligence — all analysis from DB data, no session/cart dependency."""

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# Numeric cashback rates by card_id and category
_CASHBACK_RATES = {
    "cashback_mc": {"paypal": 0.03, "default": 0.015},
    "everyday_cash": {"default": 0.02},
    "paypal_credit": {"default": 0.0},  # 0% APR benefit, not cashback
    "venmo_visa": {"top_category": 0.03, "second": 0.02, "default": 0.01},
    "debit_mc": {"chosen_category": 0.05, "default": 0.0},
    "venmo_teen": {"default": 0.0},
}

# Which card_id is best for which category (maps to get_best_card_for_category)
_CATEGORY_BEST_CARD = {
    "travel": "venmo_visa",
    "dining": "venmo_visa",
    "groceries": "debit_mc",
    "electronics": "paypal_credit",
    "baby": "cashback_mc",
    "school": "venmo_teen",
    "fashion": "everyday_cash",
    "entertainment": "venmo_visa",
    "home": "paypal_credit",
}


def _estimate_cashback_rate(card_id: str, category: str) -> float:
    """Get the effective cashback rate for a card+category combo."""
    rates = _CASHBACK_RATES.get(card_id, {})

    # Special cases
    if card_id == "venmo_visa":
        best_for = _CATEGORY_BEST_CARD.get(category)
        if best_for == "venmo_visa":
            return 0.03  # top category
        return rates.get("default", 0.01)

    if card_id == "debit_mc":
        best_for = _CATEGORY_BEST_CARD.get(category)
        if best_for == "debit_mc":
            return 0.05  # chosen category
        return 0.0

    if card_id == "cashback_mc":
        # 3% on PayPal purchases (assume all bot purchases are via PayPal)
        return 0.03

    return rates.get("default", 0.0)


def _card_id_from_name(card_name: str) -> str | None:
    """Resolve card name to card_id."""
    from bot.models.cards import get_card_by_name
    card = get_card_by_name(card_name)
    return card["id"] if card else None


async def post_purchase_card_tip(user_id: int, card_used: str) -> dict | None:
    """Analyze recent orders from DB and recommend a better card if one exists.

    Returns dict with {products, best_card, card_used_id, potential_savings} or None.
    """
    from bot.services.database import get_orders, get_user_cards
    from bot.models.cards import get_best_card_for_category, get_card_by_name, RECOMMENDABLE_CARDS

    try:
        orders = await get_orders(user_id, limit=10)
    except Exception as e:
        logger.error(f"Failed to get orders for tip: {e}")
        return None

    if not orders:
        return None

    # Filter to orders from the last 2 minutes (the ones just purchased)
    now = datetime.now(timezone.utc)
    recent = []
    for o in orders:
        created = o.get("created_at")
        if created:
            # Handle both tz-aware and naive datetimes
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created).total_seconds() < 120:
                recent.append(o)

    if not recent:
        # Fallback: use the most recent orders (might be from an older checkout)
        recent = orders[:5]

    # What card did the user pay with?
    used_card = get_card_by_name(card_used)
    used_card_id = used_card["id"] if used_card else None

    # What cards does the user already have?
    try:
        user_cards = await get_user_cards(user_id)
        owned_ids = {c.get("card_id", c.get("id", "")) for c in user_cards}
    except Exception:
        from bot.models.cards import DEFAULT_PORTFOLIO
        owned_ids = {c["id"] for c in DEFAULT_PORTFOLIO}

    # For each order category, find the best card
    total_current_cashback = 0.0
    total_best_cashback = 0.0
    best_card_for_purchase = None

    products = []
    breakdown = []  # Detailed per-item breakdown for user display
    for o in recent:
        category = o.get("category", "general")
        price = float(o.get("price", 0))
        product_name = o.get("product_name", "Item")
        products.append({"name": product_name, "price": price, "category": category})

        # Current cashback with the card they used
        current_rate = 0.0
        if used_card_id:
            current_rate = _estimate_cashback_rate(used_card_id, category)
            total_current_cashback += price * current_rate

        # Best possible card for this category
        best = get_best_card_for_category(category)
        if best:
            best_id = best["id"]
            best_rate = _estimate_cashback_rate(best_id, category)
            total_best_cashback += price * best_rate

            # Only recommend cards the user doesn't own
            if best_id not in owned_ids and best_id != used_card_id:
                best_card_for_purchase = best

            breakdown.append({
                "product": product_name,
                "price": price,
                "category": category,
                "current_card": card_used,
                "current_rate": f"{current_rate * 100:.1f}%",
                "current_cashback": round(price * current_rate, 2),
                "best_card": best.get("name", ""),
                "best_card_id": best_id,
                "best_rate": f"{best_rate * 100:.1f}%",
                "best_cashback": round(price * best_rate, 2),
                "best_benefit": best.get("reason", ""),
            })

    cashback_savings = round(total_best_cashback - total_current_cashback, 2)

    # Check for financing benefit (PayPal Credit 0% APR) — separate from cashback
    financing_tip = None
    for o in recent:
        price = float(o.get("price", 0))
        if price >= 149 and "paypal_credit" not in owned_ids:
            financing_tip = {
                "card": get_best_card_for_category("electronics"),
                "product": o.get("product_name", "Item"),
                "price": price,
                "benefit": f"0% APR for 6 months on ${price:.0f} — pay ${price / 6:.2f}/month with no interest",
            }
            break

    # Decide: recommend cashback card, financing card, or nothing
    if best_card_for_purchase and cashback_savings > 0.50:
        # Genuine cashback improvement
        return {
            "products": products,
            "best_card": best_card_for_purchase,
            "card_used": card_used,
            "benefit_type": "cashback",
            "cashback_savings": cashback_savings,
            "breakdown": breakdown,
            "financing_tip": financing_tip,
        }
    elif financing_tip and financing_tip["card"]:
        # No better cashback card, but financing available
        return {
            "products": products,
            "best_card": financing_tip["card"],
            "card_used": card_used,
            "benefit_type": "financing",
            "financing_detail": financing_tip,
            "breakdown": breakdown,
        }
    else:
        return None


async def detect_subscription_candidates(user_id: int) -> list[dict]:
    """Analyze order history for repeat purchases that could become subscriptions."""
    from bot.services.database import get_orders, get_subscriptions

    try:
        orders = await get_orders(user_id, limit=100)
    except Exception as e:
        logger.error(f"Failed to get orders for subscription detection: {e}")
        return []

    if not orders:
        return []

    # Already subscribed products
    try:
        subs = await get_subscriptions(user_id)
        subscribed_ids = {s.get("product_id", "") for s in subs}
    except Exception:
        subscribed_ids = set()

    # Group orders by product_id
    product_orders = defaultdict(list)
    for o in orders:
        pid = o.get("product_id", "")
        if pid and pid not in subscribed_ids:
            product_orders[pid].append(o)

    candidates = []
    for pid, prod_orders in product_orders.items():
        if len(prod_orders) < 2:
            continue

        # Sort by date
        prod_orders.sort(key=lambda x: x.get("created_at", datetime.min))

        # Calculate average interval
        intervals = []
        for i in range(1, len(prod_orders)):
            d1 = prod_orders[i - 1].get("created_at")
            d2 = prod_orders[i].get("created_at")
            if d1 and d2:
                delta = (d2 - d1).days
                if delta > 0:
                    intervals.append(delta)

        avg_interval = sum(intervals) / len(intervals) if intervals else 30

        # Suggest frequency
        if avg_interval <= 10:
            frequency = "weekly"
        elif avg_interval <= 21:
            frequency = "biweekly"
        else:
            frequency = "monthly"

        candidates.append({
            "product_id": pid,
            "product_name": prod_orders[0].get("product_name", "Product"),
            "times_bought": len(prod_orders),
            "avg_interval_days": round(avg_interval),
            "suggested_frequency": frequency,
            "category": prod_orders[0].get("category", ""),
            "price": float(prod_orders[0].get("price", 0)),
        })

    # Sort by times_bought descending
    candidates.sort(key=lambda x: -x["times_bought"])
    return candidates[:5]


async def analyze_spend_patterns(user_id: int) -> dict:
    """Analyze order history to recommend card optimizations based on actual spend."""
    from bot.services.database import get_orders, get_user_cards
    from bot.models.cards import get_best_card_for_category, get_card_by_id, RECOMMENDABLE_CARDS

    try:
        orders = await get_orders(user_id, limit=200)
    except Exception as e:
        logger.error(f"Failed to get orders for spend analysis: {e}")
        return {"top_categories": [], "cards_to_recommend": []}

    if not orders:
        return {"top_categories": [], "cards_to_recommend": []}

    # Owned cards
    try:
        user_cards = await get_user_cards(user_id)
        owned_ids = {c.get("card_id", c.get("id", "")) for c in user_cards}
    except Exception:
        from bot.models.cards import DEFAULT_PORTFOLIO
        owned_ids = {c["id"] for c in DEFAULT_PORTFOLIO}

    # Aggregate spend by category
    category_spend = defaultdict(float)
    category_card_used = defaultdict(lambda: defaultdict(float))

    for o in orders:
        cat = o.get("category", "general")
        price = float(o.get("price", 0))
        card = o.get("card_used", "Unknown")
        category_spend[cat] += price
        category_card_used[cat][card] += price

    # Analyze each category
    top_categories = []
    cards_to_recommend = defaultdict(lambda: {"card": None, "reasons": [], "projected_savings": 0.0})

    for cat, spend in sorted(category_spend.items(), key=lambda x: -x[1]):
        # Most used card for this category
        card_usage = category_card_used[cat]
        most_used_card = max(card_usage, key=card_usage.get) if card_usage else "Unknown"
        most_used_id = _card_id_from_name(most_used_card)

        # Best card for this category
        best = get_best_card_for_category(cat)
        best_id = best["id"] if best else None

        # Calculate potential savings
        current_rate = _estimate_cashback_rate(most_used_id, cat) if most_used_id else 0.0
        best_rate = _estimate_cashback_rate(best_id, cat) if best_id else 0.0
        savings = round((best_rate - current_rate) * spend, 2)

        entry = {
            "category": cat,
            "spend": round(spend, 2),
            "card_used": most_used_card,
            "best_card": best["name"] if best else most_used_card,
            "best_card_id": best_id,
            "current_rate": f"{current_rate * 100:.1f}%",
            "best_rate": f"{best_rate * 100:.1f}%",
            "potential_savings": max(savings, 0),
            "optimal": best_id == most_used_id or savings <= 0,
        }
        top_categories.append(entry)

        # Track cards to recommend (ones user doesn't have)
        if best_id and best_id not in owned_ids and savings > 0:
            rec = cards_to_recommend[best_id]
            rec["card"] = best
            rec["reasons"].append(f"{cat}: saves ${savings:.2f}")
            rec["projected_savings"] += savings

    recommendations = []
    for card_id, rec_data in cards_to_recommend.items():
        if rec_data["card"]:
            recommendations.append({
                "card_id": card_id,
                "card_name": rec_data["card"]["name"],
                "reasons": rec_data["reasons"],
                "projected_annual_savings": round(rec_data["projected_savings"], 2),
            })
    recommendations.sort(key=lambda x: -x["projected_annual_savings"])

    return {
        "top_categories": top_categories[:6],
        "cards_to_recommend": recommendations[:3],
        "total_spend": round(sum(category_spend.values()), 2),
        "total_orders": len(orders),
    }
