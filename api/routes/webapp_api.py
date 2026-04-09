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
    from bot.services.llm_service import ask_llm
    response = await ask_llm(q)
    return {"query": q, "response": response, "source": "gemini" if response else "fallback"}


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

    # Find the first triggerable category from cart items
    triggered = False
    for item in items:
        category = item.get("category", "")
        pattern = detect_pattern(category)
        if pattern:
            # Write as broadcast transaction — proactive loop sends to ALL users
            add_transaction(
                username="__broadcast__",
                merchant=item["name"],
                category=category,
                amount=item["price"],
                icon=item.get("icon", "💳"),
            )
            triggered = True
            break  # One proactive trigger per checkout

    return {"status": "ok", "proactive_triggered": triggered}


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
