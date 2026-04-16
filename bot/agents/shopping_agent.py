"""Shopping Agent — handles product search, cart, and checkout."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.services.catalog import get_catalog
from bot.services.session import get_session

logger = logging.getLogger(__name__)


def search_products(query: str, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Search products and return formatted message + keyboard."""
    catalog = get_catalog()
    session = get_session(user_id)

    # Build filters from user preferences
    prefs = session.get("preferences", {})
    filters = {}
    if prefs.get("color_prefer"):
        filters["color"] = prefs["color_prefer"][0]  # Use primary preferred color
    if prefs.get("color_exclude"):
        filters["color_exclude"] = prefs["color_exclude"]
    if prefs.get("brand_prefer"):
        filters["brand"] = prefs["brand_prefer"]
    if prefs.get("price_max"):
        filters["max_price"] = prefs["price_max"]

    results = catalog.search(query, filters if filters else None)

    if not results:
        # Try without filters
        results = catalog.search(query)
        if not results:
            return "🔍 No products found. Try a different search term.", None

    lines = ["🔍 *Search Results*\n"]
    buttons = []

    for i, p in enumerate(results[:6]):  # Max 6 results
        stock = "✅ In Stock" if p["in_stock"] else "❌ Out of Stock"
        colors = ", ".join(p.get("colors", [])[:3])
        lines.append(
            f"{i+1}. *{p['name']}*\n"
            f"   💰 ${p['price']} · {p['store']} · {stock}\n"
            f"   🎨 {colors}\n"
        )

        if p["in_stock"]:
            buttons.append([InlineKeyboardButton(
                f"🛒 {p['name'][:30]} — ${p['price']}",
                callback_data=f"shop:view:{p['id']}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                f"💜 Wishlist: {p['name'][:25]}",
                callback_data=f"shop:wishlist:{p['id']}"
            )])

    kb = InlineKeyboardMarkup(buttons) if buttons else None
    return "\n".join(lines), kb


def view_product(product_id: str, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Show product details with options."""
    catalog = get_catalog()
    p = catalog.get_product(product_id)
    if not p:
        return "Product not found.", None

    session = get_session(user_id)
    prefs = session.get("preferences", {})

    # Apply preferences for default selections
    default_color = prefs.get("color_prefer", [None])[0] or (p["colors"][0] if p.get("colors") else "")
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
    """Add product to user's cart."""
    catalog = get_catalog()
    p = catalog.get_product(product_id)
    if not p:
        return "Product not found."

    session = get_session(user_id)
    if "cart" not in session:
        session["cart"] = []

    # Check if already in cart
    for item in session["cart"]:
        if item["product_id"] == product_id:
            item["qty"] += 1
            return f"🛒 Updated! *{p['name']}* × {item['qty']} in cart."

    prefs = session.get("preferences", {})
    session["cart"].append({
        "product_id": product_id,
        "name": p["name"],
        "price": p["price"],
        "icon": p["icon"],
        "store": p["store"],
        "category": p.get("category", ""),
        "qty": 1,
        "color": prefs.get("color_prefer", [None])[0] or (p["colors"][0] if p.get("colors") else ""),
        "size": prefs.get("shoe_size") or prefs.get("shirt_size") or (p["sizes"][0] if p.get("sizes") else ""),
    })

    total = sum(i["price"] * i["qty"] for i in session["cart"])
    count = len(session["cart"])
    return f"🛒 *{p['name']}* added to cart!\n\nCart: {count} item(s) · Total: *${total}*"


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
    return "✅ Removed from cart."


def clear_cart(user_id: int):
    session = get_session(user_id)
    session["cart"] = []
