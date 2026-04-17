"""REST API endpoints for the Mini App."""

from fastapi import APIRouter
from bot.models.offers import CREDIT_OFFERS
from bot.models.cards import DEFAULT_PORTFOLIO, PAYPAL_CARDS

router = APIRouter()


@router.get("/user")
async def get_user(telegram_user_id: str = ""):
    """Get user info — from DB if available, defaults otherwise."""
    if telegram_user_id:
        try:
            from bot.services.database import get_user as db_get_user
            user = await db_get_user(int(telegram_user_id))
            if user:
                return {
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "initials": (user.get("name", "")[:1] or "").upper(),
                    "tenure_months": 36,
                    "credit_band": "prime",
                    "monthly_spend": 4200,
                }
        except Exception:
            pass
    return {"name": "", "email": "", "initials": "", "tenure_months": 36, "credit_band": "prime", "monthly_spend": 4200}


@router.get("/offers")
async def get_offers():
    return CREDIT_OFFERS


@router.get("/balance")
async def get_balance(telegram_user_id: str = ""):
    """Balance from user's real card portfolio."""
    cards = DEFAULT_PORTFOLIO
    if telegram_user_id:
        try:
            from bot.services.database import get_user_cards
            db_cards = await get_user_cards(int(telegram_user_id))
            if db_cards:
                cards = db_cards
        except Exception:
            pass

    total_balance = sum(c.get("default_balance", c.get("balance", 0)) for c in cards)
    total_limit = sum(c.get("default_limit", c.get("credit_limit", 0)) for c in cards)
    available = total_limit - total_balance
    utilization = round((total_balance / total_limit * 100), 1) if total_limit else 0

    return {
        "current_balance": f"${total_balance:,.2f}",
        "available_credit": f"${available:,.2f}",
        "credit_limit": f"${total_limit:,}",
        "due_date": "Apr 15",
        "min_payment": "$25.00",
        "utilization": f"{utilization}%",
    }


@router.get("/transactions")
async def get_transactions(telegram_user_id: str = ""):
    """Recent transactions from real order history, defaults if none."""
    if telegram_user_id:
        try:
            from bot.services.database import get_orders
            orders = await get_orders(int(telegram_user_id), limit=10)
            if orders:
                return [
                    {
                        "icon": "🛍",
                        "name": o.get("product_name", "Purchase"),
                        "category": o.get("category", "Shopping"),
                        "amount": f"-${o.get('price', 0)}",
                        "date": o.get("created_at", "").strftime("%b %d") if hasattr(o.get("created_at", ""), "strftime") else "",
                        "card": o.get("card_used", "PayPal"),
                    }
                    for o in orders
                ]
        except Exception:
            pass

    # Default transactions
    return [
        {"icon": "👟", "name": "Nike.com", "category": "Fashion", "amount": "-$129.00", "date": "Apr 1"},
        {"icon": "🍔", "name": "Uber Eats", "category": "Dining", "amount": "-$24.50", "date": "Mar 30"},
        {"icon": "📦", "name": "Amazon", "category": "Shopping", "amount": "-$67.99", "date": "Mar 28"},
        {"icon": "☕", "name": "Starbucks", "category": "Coffee", "amount": "-$8.75", "date": "Mar 27"},
        {"icon": "🎵", "name": "Spotify", "category": "Subscriptions", "amount": "-$9.99", "date": "Mar 25"},
    ]


@router.get("/card")
async def get_card(telegram_user_id: str = ""):
    """Primary card details from real portfolio."""
    card = DEFAULT_PORTFOLIO[0] if DEFAULT_PORTFOLIO else {}
    return {
        "number_masked": "•••• •••• •••• 4821",
        "number_full": "4821 0043 8812 4821",
        "cvv_masked": "•••",
        "cvv_full": "847",
        "holder": "",
        "expiry": "09/28",
        "product": card.get("name", "PayPal Credit Card"),
        "controls": {"online": True, "international": False, "contactless": True, "alerts": True},
    }


@router.get("/rewards")
async def get_rewards(telegram_user_id: str = ""):
    """Rewards from real card portfolio."""
    cards = DEFAULT_PORTFOLIO
    total_cashback = sum(c.get("default_rewards_earned", 0) for c in cards)
    return {
        "total_cashback": f"${total_cashback:.2f}",
        "cards": [
            {"name": c["name"], "earned": f"${c.get('default_rewards_earned', 0):.2f}",
             "rates": ", ".join(f"{k}: {v}" for k, v in c.get("rewards", {}).items())}
            for c in cards
        ],
    }


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


@router.get("/test-search")
async def test_search(q: str = "airpods"):
    """Full search pipeline test — broad search + rerank."""
    from bot.services.catalog import get_catalog
    from bot.services.llm_service import rerank_products
    import logging
    logger = logging.getLogger(__name__)

    cat = get_catalog()
    candidates = cat.search(q)
    candidate_names = [f"{p['id']}:{p['name']}" for p in candidates]

    reranked_ids = []
    if len(candidates) > 1:
        summary = cat.get_candidates_summary(candidates)
        reranked_ids = await rerank_products(q, summary)

    reranked_names = []
    for pid in reranked_ids:
        p = cat.get_product(pid)
        if p:
            reranked_names.append(f"{pid}:{p['name']}")

    return {
        "query": q,
        "broad_search": candidate_names,
        "broad_count": len(candidates),
        "reranked_ids": reranked_ids,
        "reranked_names": reranked_names,
        "reranked_count": len(reranked_ids),
    }


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

    return {
        "user_cards": user_cards,
        "total": total,
    }


@router.post("/checkout-complete")
async def checkout_complete(telegram_user_id: str = "", total: float = 0, card_used: str = ""):
    """Called by Mini App after checkout."""
    _login_store[f"checkout_{telegram_user_id}"] = {"done": True, "total": total, "card_used": card_used}
    return {"status": "ok"}


@router.get("/checkout-status")
async def checkout_status(telegram_user_id: str = ""):
    """Polled by bot for checkout completion."""
    data = _login_store.pop(f"checkout_{telegram_user_id}", None)
    if data:
        return {"done": True, "total": data["total"], "card_used": data.get("card_used", "")}
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


@router.get("/transactions-by-user")
async def get_transactions_for_user(username: str = ""):
    """Get transactions for a username."""
    from bot.services.proactive import load_transactions
    data = load_transactions()
    user_data = data.get(username.lower(), {})
    return user_data.get("transactions", [])
