"""REST API endpoints for the Mini App."""

from fastapi import APIRouter
from bot.services.mock_data import (
    MOCK_USER, MOCK_TRANSACTIONS, MOCK_BALANCE, MOCK_CARD, MOCK_REWARDS,
)
from bot.models.offers import CREDIT_OFFERS

router = APIRouter()


@router.get("/user")
async def get_user():
    return MOCK_USER


@router.get("/offers")
async def get_offers():
    return CREDIT_OFFERS


@router.get("/balance")
async def get_balance():
    return MOCK_BALANCE


@router.get("/transactions")
async def get_transactions():
    return MOCK_TRANSACTIONS


@router.get("/card")
async def get_card():
    return MOCK_CARD


@router.get("/rewards")
async def get_rewards():
    return MOCK_REWARDS


# Store login state per user (Mini App writes, bot reads)
_login_store: dict[str, dict] = {}


@router.post("/login-complete")
async def login_complete(telegram_user_id: str = "", name: str = "", email: str = ""):
    """Called by Mini App after successful login."""
    _login_store[telegram_user_id] = {"name": name, "email": email, "done": True}
    return {"status": "ok"}


@router.get("/login-status")
async def login_status(telegram_user_id: str = ""):
    """Polled by bot to check if user completed login."""
    data = _login_store.pop(telegram_user_id, None)
    if data:
        return {"done": True, "name": data["name"], "email": data["email"]}
    return {"done": False}


@router.post("/apply")
async def apply(offer_index: int = 0):
    offer = CREDIT_OFFERS[offer_index] if offer_index < len(CREDIT_OFFERS) else CREDIT_OFFERS[0]
    return {
        "status": "approved",
        "product": offer["name"],
        "limit": offer["amount"],
        "decision_ms": 3100,
    }


@router.get("/registered-users")
async def registered_users():
    """View all registered bot users (username → chat_id)."""
    from bot.services.user_store import get_all_users
    users = get_all_users()
    return {"count": len(users), "users": users}


@router.get("/test-llm")
async def test_llm(q: str = "recommend a travel card"):
    from bot.services.llm_service import classify_intent, general_response
    intent = await classify_intent(q, [])
    resp = await general_response(q, [])
    return {"query": q, "intent": intent, "response": resp}


@router.post("/form-complete")
async def form_complete(telegram_user_id: str = "", name: str = "", pan: str = ""):
    """Called by Mini App after form submission."""
    _login_store[f"form_{telegram_user_id}"] = {"name": name, "pan": pan, "done": True}
    return {"status": "ok"}


@router.get("/form-status")
async def form_status(telegram_user_id: str = ""):
    """Polled by bot to check if user completed the form."""
    data = _login_store.pop(f"form_{telegram_user_id}", None)
    if data:
        return {"done": True, "name": data["name"], "pan": data["pan"]}
    return {"done": False}


@router.post("/checkout")
async def checkout(data: dict):
    """Called by e-commerce site on PayPal checkout — broadcasts to all bot users."""
    from bot.services.proactive import add_transaction, detect_pattern
    items = data.get("items", [])
    payment_method = data.get("payment_method", "")

    if payment_method != "paypal":
        return {"status": "ok", "proactive_triggered": False}

    # Find the highest-value triggerable item in cart
    best_item = None
    best_value = 0
    for item in items:
        category = item.get("category", "")
        pattern = detect_pattern(category)
        if pattern:
            value = item.get("price", 0) * item.get("qty", 1)
            if value > best_value:
                best_value = value
                best_item = item

    triggered = False
    if best_item:
        add_transaction(
            username="__broadcast__",
            merchant=best_item["name"],
            category=best_item["category"],
            amount=best_item["price"],
            icon=best_item.get("icon", "💳"),
        )
        triggered = True

    return {"status": "ok", "proactive_triggered": triggered}


@router.get("/cart-data")
async def get_cart_data(telegram_user_id: str = ""):
    """Get cart data for Mini App checkout page."""
    try:
        uid = int(telegram_user_id)
        from bot.services.session import get_session
        session = get_session(uid)
        cart = session.get("cart", [])
        name = session.get("name", "User")
        email = session.get("email", "")
        total = sum(i["price"] * i["qty"] for i in cart)
        return {"cart": cart, "total": total, "name": name, "email": email}
    except Exception:
        return {"cart": [], "total": 0, "name": "", "email": ""}


@router.get("/card-recommendations")
async def card_recommendations(total: float = 0, category: str = "general"):
    """Get credit card recommendations for checkout — LLM-powered."""
    from bot.models.cards import PAYPAL_CARDS, DEFAULT_PORTFOLIO, RECOMMENDABLE_CARDS

    # User's current cards with mock balances
    user_cards = []
    for c in DEFAULT_PORTFOLIO:
        rewards_desc = ", ".join(f"{k}: {v}" for k, v in c.get("rewards", {}).items())
        # Calculate estimated reward for this purchase
        reward_amount = 0
        if "3%" in rewards_desc:
            reward_amount = round(total * 0.03, 2)
        elif "2%" in rewards_desc:
            reward_amount = round(total * 0.02, 2)
        elif "1.5%" in rewards_desc:
            reward_amount = round(total * 0.015, 2)

        user_cards.append({
            "id": c["id"],
            "name": c["name"],
            "type": c["type"],
            "rewards_desc": rewards_desc,
            "reward_amount": reward_amount,
            "annual_fee": c.get("annual_fee", "$0"),
            "balance": c.get("default_balance", 0),
            "limit": c.get("default_limit", 0),
            "owned": True,
        })

    # Sort by reward amount descending — best card first
    user_cards.sort(key=lambda x: -x["reward_amount"])
    if user_cards:
        user_cards[0]["recommended"] = True

    # Cards user doesn't have but could benefit from
    suggestions = []
    for c in RECOMMENDABLE_CARDS:
        suggestion = {
            "id": c["id"],
            "name": c["name"],
            "type": c["type"],
            "annual_fee": c.get("annual_fee", "$0"),
            "owned": False,
        }
        # Calculate potential benefit
        rewards = c.get("rewards", {})
        if "0% APR" in str(rewards) and total >= 149:
            months = 6
            monthly = round(total / months, 2)
            suggestion["benefit"] = f"0% APR for {months} months — pay ${monthly}/month interest-free"
            suggestion["highlight"] = True
        elif "3%" in str(rewards):
            suggestion["benefit"] = f"Up to 3% cashback (${round(total * 0.03, 2)}) — auto-detects top spending category"
        elif "5%" in str(rewards):
            suggestion["benefit"] = f"5% cashback on chosen category (${round(total * 0.05, 2)}/month)"
        else:
            suggestion["benefit"] = c.get("special", "")

        if suggestion.get("benefit"):
            suggestions.append(suggestion)

    return {
        "user_cards": user_cards,
        "suggestions": suggestions[:2],  # Max 2 suggestions
        "total": total,
    }


@router.post("/checkout-complete")
async def checkout_complete(telegram_user_id: str = "", total: float = 0):
    """Called by Mini App after checkout."""
    _login_store[f"checkout_{telegram_user_id}"] = {"done": True, "total": total}
    return {"status": "ok"}


@router.get("/checkout-status")
async def checkout_status(telegram_user_id: str = ""):
    """Polled by bot for checkout completion."""
    data = _login_store.pop(f"checkout_{telegram_user_id}", None)
    if data:
        return {"done": True, "total": data["total"]}
    return {"done": False}


@router.post("/submit-transaction")
async def submit_transaction(data: dict):
    """Called by transaction web page."""
    from bot.services.proactive import add_transaction
    username = data.get("username", "").lower().strip()
    merchant = data.get("merchant", "")
    category = data.get("category", "other")
    amount = float(data.get("amount", 0))

    # Auto-detect icon from merchant
    icons = {
        "Singapore Airlines": "✈️", "Emirates": "✈️", "Marriott Hotels": "🏨",
        "Booking.com": "🏨", "Uber (Airport)": "🚕",
        "FirstCry": "👶", "Mothercare": "👶", "Dr. Mehta Clinic": "🏥", "BabyCenter Store": "🍼",
        "Uber Eats": "🍔", "DoorDash": "🍕", "Starbucks": "☕",
        "Amazon": "📦", "Nike.com": "👟", "Target": "🛒",
    }
    icon = icons.get(merchant, "💳")

    result = add_transaction(username, merchant, category, amount, icon)
    return result


@router.get("/transactions")
async def get_transactions_for_user(username: str = ""):
    """Get transactions for a username."""
    from bot.services.proactive import load_transactions
    data = load_transactions()
    user_data = data.get(username.lower(), {})
    return user_data.get("transactions", [])
