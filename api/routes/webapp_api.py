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


# ── Debug / Test endpoints ──

@router.get("/test-flow")
async def test_full_flow(uid: int = 12345):
    """Simulate full post-purchase flow: add order → card tip → subscription check.
    Hit: /api/test-flow?uid=12345
    """
    import logging
    log = logging.getLogger("test-flow")
    results = {"steps": []}

    # Step 1: Save a test order to DB
    try:
        from bot.services.database import add_order, get_orders
        await add_order(uid, "sb-007", "Apple AirPods Pro 2", 249.0, "electronics", "PayPal Cashback Mastercard")
        results["steps"].append({"step": "1_save_order", "status": "ok"})
    except Exception as e:
        results["steps"].append({"step": "1_save_order", "status": "error", "detail": str(e)})
        return results

    # Step 2: Read orders back from DB
    try:
        orders = await get_orders(uid, limit=5)
        results["steps"].append({
            "step": "2_read_orders",
            "status": "ok",
            "count": len(orders),
            "latest": {"name": orders[0].get("product_name"), "price": float(orders[0].get("price", 0)), "category": orders[0].get("category"), "card": orders[0].get("card_used")} if orders else None,
        })
    except Exception as e:
        results["steps"].append({"step": "2_read_orders", "status": "error", "detail": str(e)})
        return results

    # Step 3: Post-purchase card tip
    try:
        from bot.agents.intelligence import post_purchase_card_tip
        tip_data = await post_purchase_card_tip(uid, "PayPal Cashback Mastercard")
        if tip_data:
            results["steps"].append({
                "step": "3_card_tip",
                "status": "ok",
                "best_card": tip_data["best_card"]["name"],
                "savings": tip_data["potential_savings"],
                "products": tip_data["products"],
            })
        else:
            results["steps"].append({"step": "3_card_tip", "status": "ok", "result": "no_better_card"})
    except Exception as e:
        results["steps"].append({"step": "3_card_tip", "status": "error", "detail": str(e)})

    # Step 4: LLM enrichment (generate human-readable tip)
    if any(s["step"] == "3_card_tip" and s.get("best_card") for s in results["steps"]):
        try:
            from bot.services.llm_service import credit_enrichment
            from bot.models.cards import RECOMMENDABLE_CARDS
            tip_step = next(s for s in results["steps"] if s["step"] == "3_card_tip")
            rec_portfolio = [{"card_id": c["id"]} for c in RECOMMENDABLE_CARDS]
            tip_text = await credit_enrichment(
                tip_step["products"], rec_portfolio,
                paid_with="PayPal Cashback Mastercard (paypal_purchases: 3% cashback, everything_else: 1.5% cashback)"
            )
            results["steps"].append({"step": "4_llm_tip", "status": "ok", "tip": tip_text})
        except Exception as e:
            results["steps"].append({"step": "4_llm_tip", "status": "error", "detail": str(e)})

    # Step 5: Subscription detection
    try:
        from bot.agents.intelligence import detect_subscription_candidates
        candidates = await detect_subscription_candidates(uid)
        results["steps"].append({
            "step": "5_subscription_check",
            "status": "ok",
            "candidates": [{"name": c["product_name"], "times": c["times_bought"], "freq": c["suggested_frequency"]} for c in candidates],
        })
    except Exception as e:
        results["steps"].append({"step": "5_subscription_check", "status": "error", "detail": str(e)})

    # Step 6: Spend analysis
    try:
        from bot.agents.intelligence import analyze_spend_patterns
        analysis = await analyze_spend_patterns(uid)
        results["steps"].append({
            "step": "6_spend_analysis",
            "status": "ok",
            "total_spend": analysis.get("total_spend"),
            "total_orders": analysis.get("total_orders"),
            "top_categories": analysis.get("top_categories", [])[:3],
            "cards_to_recommend": analysis.get("cards_to_recommend", []),
        })
    except Exception as e:
        results["steps"].append({"step": "6_spend_analysis", "status": "error", "detail": str(e)})

    return results


@router.get("/test-orders")
async def test_orders(uid: int = 12345):
    """Check what orders exist for a user. Hit: /api/test-orders?uid=12345"""
    try:
        from bot.services.database import get_orders
        orders = await get_orders(uid, limit=20)
        return {
            "user_id": uid,
            "count": len(orders),
            "orders": [
                {"id": o.get("id"), "product": o.get("product_name"), "price": float(o.get("price", 0)),
                 "category": o.get("category"), "card": o.get("card_used"),
                 "date": str(o.get("created_at", ""))}
                for o in orders
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/outstock")
@router.get("/outstock")
async def outstock_product(product_id: str = ""):
    """Mark a product as out of stock. Hit: /api/outstock?product_id=sb-001"""
    if not product_id:
        return {"error": "product_id required"}
    from bot.services.catalog import get_catalog
    catalog = get_catalog()
    product = catalog.get_product(product_id)
    if not product:
        return {"error": f"Product '{product_id}' not found"}
    catalog.update_stock(product_id, False)
    # Reset wishlist notifications so users can be re-notified on next restock
    try:
        from bot.services.database import mark_wishlist_notified
        # We don't reset here — notified stays TRUE so they don't get spammed
    except Exception:
        pass
    return {"product_id": product_id, "name": product["name"], "in_stock": False}


@router.post("/restock")
@router.get("/restock")
async def restock_product(product_id: str = ""):
    """Mark a product as back in stock and notify all wishlisted users.
    Hit: POST /api/restock?product_id=sb-001
    """
    if not product_id:
        return {"error": "product_id required"}

    import logging
    log = logging.getLogger("restock")
    results = {"product_id": product_id, "notifications_sent": 0, "users_notified": []}

    # 1. Update catalog stock
    try:
        from bot.services.catalog import get_catalog
        catalog = get_catalog()
        product = catalog.get_product(product_id)
        if not product:
            return {"error": f"Product '{product_id}' not found in catalog"}
        catalog.update_stock(product_id, True)
        results["product_name"] = product["name"]
        results["stock_updated"] = True
    except Exception as e:
        return {"error": f"Failed to update stock: {e}"}

    # 2. Find wishlisted users
    try:
        from bot.services.database import get_wishlist_users_for_product, mark_wishlist_notified
        users = await get_wishlist_users_for_product(product_id)
        results["wishlisted_users"] = len(users)
    except Exception as e:
        log.error(f"Failed to query wishlist: {e}")
        return {**results, "error": f"Stock updated but wishlist query failed: {e}"}

    if not users:
        return {**results, "message": "Stock updated. No users to notify."}

    # 3. Send notifications
    from bot.services.bot_ref import get_bot
    bot = get_bot()
    if not bot:
        return {**results, "error": "Stock updated but bot not available for notifications"}

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    for user in users:
        try:
            tid = user["telegram_id"]
            pname = user["product_name"]
            await bot.send_message(
                chat_id=tid,
                text=(
                    f"🔔 *Back in Stock!*\n\n"
                    f"Great news! *{pname}* is available again.\n"
                    f"Grab it before it sells out!"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🛒 Add to Cart", callback_data=f"shop:add:{product_id}")],
                    [InlineKeyboardButton(f"🗑 Remove from Wishlist", callback_data=f"wishlist:remove:{product_id}")],
                ]),
            )
            results["notifications_sent"] += 1
            results["users_notified"].append(tid)
            log.info(f"Notified user {tid} about restock: {pname}")
        except Exception as e:
            log.error(f"Failed to notify user {user['telegram_id']}: {e}")

    # 4. Mark as notified
    try:
        await mark_wishlist_notified(product_id)
    except Exception as e:
        log.error(f"Failed to mark notified: {e}")

    return results
