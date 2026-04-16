"""Shopping Agent — handles product search, cart, checkout."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.orchestrator import OrchestratorResult
from bot.services import llm_service
from bot.services.catalog import get_catalog
from bot.services.session import get_session

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a PayPal Shopping Assistant. You help users find and buy products.

You have these tools:
- search_products: search for products. Use when user asks for a SPECIFIC product or product type (e.g. "Nike Jordan shoes", "headphones", "baby diapers"). Do NOT use when user says only a brand name without product type.
- show_cart: show the user's shopping cart

Key behaviors:
- If user says only a brand name (e.g. "Nike", "Apple") without specifying what type of product → ask "What type of Nike product are you looking for — shoes, clothing, or accessories?"
- If user says "show more" or "more options" → look at conversation history for the previous search, and search with a broader query
- When user asks about a product, be helpful and specific

Be concise and natural."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products to buy. Use when user mentions a product TYPE (shoes, headphones, diapers, laptop). Extract the search query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Product search query, e.g. 'Nike Jordan shoes', 'headphones', 'baby diapers'"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_cart",
            "description": "Show the user's shopping cart contents.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


class ShoppingAgent:
    async def handle(self, message: str, user_id: int,
                     history: list[dict], session: dict) -> OrchestratorResult:
        """Handle shopping-related intent."""

        messages = []
        if history:
            for m in history[-10:]:
                messages.append({
                    "role": m["role"] if m["role"] == "user" else "assistant",
                    "content": m["content"],
                })
        messages.append({"role": "user", "content": message})

        result = await llm_service.call_agent(SYSTEM_PROMPT, TOOLS, messages)

        llm_message = result.get("message")
        tool_call = result.get("tool_call")

        response = OrchestratorResult(intent="shopping")

        if tool_call and tool_call["name"] == "search_products":
            query = tool_call["args"].get("query", message)
            # Pass original message for negation handling ("not iphone")
            products = await self._search_and_rerank(query, user_id, original_message=message)

            if products:
                if llm_message:
                    response.message = llm_message
                response.products = products
                # Store what was shown in session for "show more"
                session["last_search"] = query
            else:
                response.message = "🔍 No products found. Try a different search term."

        elif tool_call and tool_call["name"] == "show_cart":
            response.tool_action = {"name": "show_cart", "args": {}}
            if llm_message:
                response.message = llm_message

        else:
            # No tool call — just conversational (e.g. "What type of Nike product?")
            response.message = llm_message or "What are you looking for? I can help you find products."

        return response

    async def _search_and_rerank(self, query: str, user_id: int, original_message: str = "") -> list[dict]:
        """Broad search + LLM reranking → product cards."""
        catalog = get_catalog()
        session = get_session(user_id)

        # Build filters from preferences
        prefs = session.get("preferences", {})
        filters = {}
        if prefs.get("color_prefer"):
            filters["color"] = prefs["color_prefer"][0] if isinstance(prefs["color_prefer"], list) else prefs["color_prefer"]
        if prefs.get("color_exclude"):
            filters["color_exclude"] = prefs["color_exclude"]

        # Step 1: Broad search
        candidates = catalog.search(query, filters if filters else None)
        if not candidates:
            candidates = catalog.search(query)
        if not candidates:
            return []

        # Step 2: LLM reranking
        if len(candidates) > 4:
            summary = catalog.get_candidates_summary(candidates)
            rerank_query = original_message if original_message else query
            selected_ids = await llm_service.rerank_products(rerank_query, summary)
            if selected_ids:
                id_to_product = {p["id"]: p for p in candidates}
                reranked = [id_to_product[pid] for pid in selected_ids if pid in id_to_product]
                if reranked:
                    candidates = reranked

        results = candidates[:4]

        # Format as cards for Telegram
        cards = []
        for p in results:
            stock = "✅ In Stock" if p["in_stock"] else "❌ Out of Stock"
            colors = ", ".join(p.get("colors", [])[:3])

            caption = (
                f"*{p['name']}*\n"
                f"💰 *${p['price']}* · 🏪 {p['store']}\n"
                f"{stock} · 🎨 {colors}"
            )

            if p["in_stock"]:
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🛒 Add to Cart", callback_data=f"shop:add:{p['id']}"),
                        InlineKeyboardButton("📋 Details", callback_data=f"shop:view:{p['id']}"),
                    ],
                ])
            else:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💜 Add to Wishlist", callback_data=f"shop:wishlist:{p['id']}")],
                ])

            cards.append({
                "image": p.get("image", ""),
                "caption": caption,
                "keyboard": kb,
                "icon": p["icon"],
                "name": p["name"],
                "price": p["price"],
                "category": p.get("category", ""),
                "product_id": p["id"],
            })

        return cards


# ── Standalone functions used by callbacks.py (unchanged) ──

def view_product(product_id: str, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Show product details with options."""
    catalog = get_catalog()
    p = catalog.get_product(product_id)
    if not p:
        return "Product not found.", None

    session = get_session(user_id)
    prefs = session.get("preferences", {})
    default_color = prefs.get("color_prefer", [None])
    if isinstance(default_color, list):
        default_color = default_color[0] if default_color else ""
    default_size = prefs.get("shoe_size") or prefs.get("shirt_size") or (p["sizes"][0] if p.get("sizes") else "")

    colors = " · ".join(p.get("colors", []))
    sizes = " · ".join(p.get("sizes", []))
    stock = "✅ In Stock" if p["in_stock"] else "❌ Out of Stock"

    pref_note = ""
    if default_color and default_color in p.get("colors", []):
        pref_note += f"\n🎨 Color: *{default_color}* (your preference)"
    if default_size and default_size in p.get("sizes", []):
        pref_note += f"\n📏 Size: *{default_size}* (your preference)"

    msg = (
        f"{p['icon']} *{p['name']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 Brand: {p.get('brand', 'N/A')}\n"
        f"💰 Price: *${p['price']}*\n"
        f"🏪 Store: {p['store']}\n"
        f"📦 {stock}\n"
        f"🎨 Colors: {colors}\n"
        f"📏 Sizes: {sizes}"
        f"{pref_note}"
    )

    if p["in_stock"]:
        buttons = [
            [InlineKeyboardButton("🛒 Add to Cart", callback_data=f"shop:add:{product_id}")],
            [InlineKeyboardButton("🔙 Back to Search", callback_data="shop:back")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton("💜 Add to Wishlist", callback_data=f"shop:wishlist:{product_id}")],
            [InlineKeyboardButton("🔙 Back to Search", callback_data="shop:back")],
        ]

    return msg, InlineKeyboardMarkup(buttons)


def add_to_cart(product_id: str, user_id: int) -> str:
    """Add product to session cart + DB."""
    catalog = get_catalog()
    p = catalog.get_product(product_id)
    if not p:
        return "Product not found."

    session = get_session(user_id)
    if "cart" not in session:
        session["cart"] = []

    for item in session["cart"]:
        if item["product_id"] == product_id:
            item["qty"] += 1
            # Also update DB
            _db_add_to_cart(user_id, p)
            return f"🛒 Updated! *{p['name']}* × {item['qty']} in cart."

    prefs = session.get("preferences", {})
    color_pref = prefs.get("color_prefer", [None])
    if isinstance(color_pref, list):
        color_pref = color_pref[0] if color_pref else ""

    session["cart"].append({
        "product_id": product_id,
        "name": p["name"],
        "price": p["price"],
        "icon": p["icon"],
        "store": p["store"],
        "category": p.get("category", ""),
        "qty": 1,
        "color": color_pref or (p["colors"][0] if p.get("colors") else ""),
        "size": prefs.get("shoe_size") or prefs.get("shirt_size") or (p["sizes"][0] if p.get("sizes") else ""),
    })

    # Write to DB
    _db_add_to_cart(user_id, p)

    total = sum(i["price"] * i["qty"] for i in session["cart"])
    count = len(session["cart"])
    return f"🛒 *{p['name']}* added to cart!\n\nCart: {count} item(s) · Total: *${total}*"


def _db_add_to_cart(user_id: int, product: dict):
    """Fire-and-forget DB cart write."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_async_db_add_cart(user_id, product))
    except Exception:
        pass


async def _async_db_add_cart(user_id: int, product: dict):
    try:
        from bot.services.database import add_to_cart as db_add
        await db_add(
            user_id, product["id"], product["name"], product["price"],
            product.get("icon", ""), product.get("store", ""), product.get("category", ""),
        )
    except Exception:
        pass


def get_cart_message(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Show cart contents."""
    session = get_session(user_id)
    cart = session.get("cart", [])

    if not cart:
        return "🛒 Your cart is empty. Search for products to get started!", None

    lines = ["🛒 *Your Cart*\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"]
    buttons = []

    for item in cart:
        lines.append(
            f"{item['icon']} *{item['name']}*\n"
            f"   ${item['price']} × {item['qty']} = *${item['price'] * item['qty']}*\n"
            f"   {item.get('color', '')} · {item.get('size', '')} · {item['store']}\n"
        )
        buttons.append([InlineKeyboardButton(
            f"❌ Remove {item['name'][:20]}",
            callback_data=f"shop:remove:{item['product_id']}"
        )])

    total = sum(i["price"] * i["qty"] for i in cart)
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 *Total: ${total}*")

    buttons.append([InlineKeyboardButton("💳 Checkout via PayPal", callback_data="shop:checkout")])
    buttons.append([InlineKeyboardButton("🛍 Continue Shopping", callback_data="shop:back")])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)


def remove_from_cart(product_id: str, user_id: int) -> str:
    session = get_session(user_id)
    cart = session.get("cart", [])
    session["cart"] = [i for i in cart if i["product_id"] != product_id]
    # DB remove
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_async_db_remove_cart(user_id, product_id))
    except Exception:
        pass
    return "✅ Removed from cart."


async def _async_db_remove_cart(user_id: int, product_id: str):
    try:
        from bot.services.database import remove_from_cart as db_remove
        await db_remove(user_id, product_id)
    except Exception:
        pass


def clear_cart(user_id: int):
    session = get_session(user_id)
    session["cart"] = []
    # DB clear
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_async_db_clear_cart(user_id))
    except Exception:
        pass


async def _async_db_clear_cart(user_id: int):
    try:
        from bot.services.database import clear_cart as db_clear
        await db_clear(user_id)
    except Exception:
        pass
