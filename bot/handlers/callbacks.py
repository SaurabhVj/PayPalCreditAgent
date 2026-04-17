"""Inline button callback handler — full v9 flow with dummy login."""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from bot.config import WEBAPP_URL
from bot.services.session import (
    get_state, set_state, set_selected_offer, get_selected_offer,
)
from bot.models.state import FlowState
from bot.models.offers import CREDIT_OFFERS
from bot.utils.keyboards import (
    offers_keyboard, confirm_keyboard, post_approval_keyboard,
    main_menu_keyboard, portfolio_keyboard, collections_keyboard,
    collections_plan_keyboard, proactive_keyboard,
)
from bot.utils.formatters import (
    all_offers_message, confirm_message, approval_message,
    balance_message, statement_message,
    portfolio_message, portfolio_optimize_message, portfolio_compare_message,
    collections_message, collections_hardship_message,
    collections_options_message, collections_plan_confirmed,
)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # ── Topic selections ──
    if data == "topic:credit":
        await _handle_credit_start(query, user_id)

    elif data == "topic:balance":
        await query.message.reply_text(
            balance_message(), parse_mode="Markdown",
            reply_markup=_post_balance_keyboard(),
        )

    elif data == "topic:rewards":
        from bot.utils.formatters import rewards_message
        await query.message.reply_text(rewards_message(), parse_mode="Markdown")

    elif data == "topic:portfolio":
        await _handle_portfolio(query)

    elif data == "topic:collections":
        await _handle_collections(query)

    elif data == "topic:shop":
        await query.message.reply_text("🛍 What would you like to shop for? Type a product name like:\n\n• _Nike Jordan_\n• _headphones_\n• _baby diapers_\n• _coffee machine_", parse_mode="Markdown")

    elif data == "topic:credit_menu":
        from bot.utils.keyboards import credit_menu_keyboard
        await query.message.reply_text("💳 *Credit Services*\n\nWhat would you like to do?", parse_mode="Markdown", reply_markup=credit_menu_keyboard())

    elif data == "topic:cart":
        from bot.agents.shopping_agent import get_cart_message
        msg, kb = get_cart_message(user_id)
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif data == "topic:main_menu" or data == "topic:menu_show":
        await query.message.reply_text("Choose an option:", reply_markup=main_menu_keyboard())

    # ── Auth flow — after Mini App login completes ──
    elif data == "auth:connected":
        await _handle_post_login(query, user_id)

    # ── Offer selection ──
    elif data.startswith("offer:"):
        index = int(data.split(":")[1])
        set_selected_offer(user_id, index)
        set_state(user_id, FlowState.SELECTED)

        o = CREDIT_OFFERS[index]
        await query.message.reply_text(
            f"*{o['name']}*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💳 Credit Limit: *{o['amount']}*\n"
            f"📋 {o['detail']}\n"
            f"📊 Match Score: *{o['score']}%*\n"
            f"🏷 _{o['tag']}_\n\n"
            f"Would you like to go ahead?",
            parse_mode="Markdown",
            reply_markup=_offer_action_keyboard(),
        )

    # ── Offer actions ──
    elif data == "action:apply_now":
        await _handle_application_form(query, user_id)

    elif data == "action:tell_more":
        await _handle_tell_more(query, user_id)

    elif data == "action:submit":
        await _handle_submit(query, user_id)

    elif data == "action:back_offers":
        set_state(user_id, FlowState.OFFERS_SHOWN)
        await query.message.reply_text(
            "Of course! Here are all three options again:\n\n" + all_offers_message(),
            parse_mode="Markdown",
            reply_markup=offers_keyboard(),
        )

    elif data == "action:statement":
        await query.message.reply_text(
            statement_message(), parse_mode="Markdown",
        )

    elif data == "action:card":
        from bot.services.session import get_session
        name = get_session(user_id).get("name", "User")
        await query.message.reply_text(
            _card_manage_message(name), parse_mode="Markdown",
            reply_markup=_card_action_keyboard(),
        )

    # ── Card actions ──
    elif data.startswith("card:"):
        await _handle_card_action(query, data.split(":")[1])

    # ── Portfolio actions ──
    elif data == "portfolio:optimize":
        # Dynamic spend analysis from DB order history
        try:
            from bot.agents.intelligence import analyze_spend_patterns
            from bot.utils.formatters import dynamic_portfolio_optimize_message
            analysis = await analyze_spend_patterns(user_id)
            if analysis.get("top_categories"):
                await query.message.reply_text(dynamic_portfolio_optimize_message(analysis), parse_mode="Markdown")
            else:
                await query.message.reply_text(portfolio_optimize_message(), parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(portfolio_optimize_message(), parse_mode="Markdown")

    elif data == "portfolio:compare":
        await query.message.reply_text(portfolio_compare_message(), parse_mode="Markdown")

    elif data == "portfolio:whatif":
        await query.message.reply_text(
            "📈 *What-If Analysis*\n\n"
            "Type a question like:\n"
            '• _"What if I spend more on travel?"_\n'
            '• _"What if I reduce dining and increase shopping?"_\n'
            '• _"Which card is better for $10K travel spend?"_\n\n'
            "I'll calculate projected rewards for you.",
            parse_mode="Markdown",
        )

    # ── Collections actions ──
    elif data == "collect:options":
        await query.message.reply_text(collections_options_message(), parse_mode="Markdown", reply_markup=collections_plan_keyboard())

    elif data == "collect:hardship":
        await query.message.reply_text(collections_hardship_message(), parse_mode="Markdown")
        await asyncio.sleep(1)
        await query.message.reply_text(collections_options_message(), parse_mode="Markdown", reply_markup=collections_plan_keyboard())

    elif data == "collect:dispute":
        await query.message.reply_text(
            "❌ *Dispute Filed*\n\n"
            "Your dispute has been recorded. Our team will review\n"
            "within 5 business days and contact you with findings.\n\n"
            "During the review:\n"
            "• No late fees will accrue\n"
            "• No credit reporting changes\n"
            "• You'll receive updates via this chat",
            parse_mode="Markdown",
        )

    elif data.startswith("collect:plan_"):
        plan = data.split("_")[1].upper()
        await query.message.chat.send_action(ChatAction.TYPING)
        await asyncio.sleep(1.5)
        await query.message.reply_text(collections_plan_confirmed(plan), parse_mode="Markdown")

    # ── Proactive offer response ──
    elif data.startswith("proactive:yes"):
        pattern = data.split(":")[2] if len(data.split(":")) > 2 else "travel"
        await _handle_proactive_offer(query, user_id, pattern)

    elif data == "proactive:no":
        await query.message.reply_text("No worries! I'll be here if you change your mind. 😊")

    elif data.startswith("proactive:apply"):
        pattern = data.split(":")[2] if len(data.split(":")) > 2 else "travel"
        await _handle_proactive_apply(query, user_id, pattern)

    # ── Shopping callbacks ──
    elif data.startswith("shop:view:"):
        product_id = data.split(":", 2)[2]
        from bot.agents.shopping_agent import view_product
        msg, kb = view_product(product_id, user_id)
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("shop:add:"):
        product_id = data.split(":", 2)[2]
        from bot.agents.shopping_agent import add_to_cart, get_cart_message
        result = add_to_cart(product_id, user_id)
        await query.message.reply_text(result, parse_mode="Markdown")
        msg, kb = get_cart_message(user_id)
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("shop:remove:"):
        product_id = data.split(":", 2)[2]
        from bot.agents.shopping_agent import remove_from_cart, get_cart_message
        remove_from_cart(product_id, user_id)
        msg, kb = get_cart_message(user_id)
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif data == "shop:checkout":
        from bot.services.session import get_session as _get_sess
        sess = _get_sess(user_id)

        # Credit card recommendation before checkout
        cart = sess.get("cart", [])
        if cart:
            try:
                from bot.services.llm_service import credit_enrichment
                from bot.models.cards import DEFAULT_PORTFOLIO
                portfolio = [{"card_id": c["id"], "balance": c.get("default_balance", 0), "credit_limit": c.get("default_limit", 0)} for c in DEFAULT_PORTFOLIO]
                import logging
                logging.getLogger(__name__).info(f"Credit enrichment: {len(cart)} items, {len(portfolio)} cards")
                tip = await credit_enrichment(cart, portfolio)
                logging.getLogger(__name__).info(f"Credit tip: {tip}")
                if tip:
                    await query.message.reply_text(tip)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Credit enrichment failed: {e}")

        if not sess.get("name"):
            # Need to login first
            login_url = f"{WEBAPP_URL}/webapp?mode=login"
            cart = sess.get("cart", [])
            total = sum(i["price"] * i["qty"] for i in cart)
            await query.message.reply_text(
                f"💳 *Checkout — ${total}*\n\n"
                "Connect your PayPal account to complete the purchase.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Connect with PayPal", web_app=WebAppInfo(url=login_url))],
                ]),
            )
            asyncio.create_task(_poll_login_then_checkout(query, user_id))
        else:
            # Already connected — open Mini App checkout
            cart = sess.get("cart", [])
            total = sum(i["price"] * i["qty"] for i in cart)
            name = sess.get("name", "User")
            # Encode cart summary into URL params so Mini App doesn't need API call
            import urllib.parse
            items_param = urllib.parse.quote(",".join(f"{i['icon']}{i['name']}|{i['price']}|{i['qty']}" for i in cart[:5]))
            checkout_url = f"{WEBAPP_URL}/webapp?mode=checkout&uid={user_id}&total={total}&name={urllib.parse.quote(name)}&items={items_param}"
            await query.message.reply_text(
                f"💳 *Checkout — ${total}*\n\n"
                f"Tap below to review and pay:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Pay with PayPal", web_app=WebAppInfo(url=checkout_url))],
                ]),
            )
            asyncio.create_task(_poll_checkout_complete(query, user_id))

    elif data == "shop:back":
        await query.message.reply_text("🛍 What would you like to search for? Type a product name.")

    elif data == "shop:pay":
        await _handle_shop_pay(query, user_id)

    elif data == "shop:showcart":
        from bot.agents.shopping_agent import get_cart_message
        msg, kb = get_cart_message(user_id)
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("shop:wishlist:"):
        product_id = data.split(":", 2)[2]
        from bot.services.catalog import get_catalog
        p = get_catalog().get_product(product_id)
        name = p["name"] if p else "Item"
        # Store in session
        session = get_session(user_id)
        if "wishlist" not in session:
            session["wishlist"] = []
        if product_id not in [w["product_id"] for w in session["wishlist"]]:
            session["wishlist"].append({"product_id": product_id, "name": name})
        # Store in DB
        try:
            from bot.services.database import add_to_wishlist
            asyncio.create_task(add_to_wishlist(user_id, product_id, name))
        except Exception:
            pass
        await query.message.reply_text(f"💜 *{name}* added to your wishlist.\nI'll notify you when it's back in stock!", parse_mode="Markdown")

    elif data.startswith("subscribe:setup:"):
        # subscribe:setup:{product_id}:{frequency}
        parts = data.split(":")
        product_id = parts[2] if len(parts) > 2 else ""
        frequency = parts[3] if len(parts) > 3 else "monthly"
        try:
            from bot.services.database import add_subscription
            from bot.services.catalog import get_catalog
            p = get_catalog().get_product(product_id)
            product_name = p["name"] if p else "Product"
            from datetime import date, timedelta
            intervals = {"weekly": 7, "biweekly": 14, "monthly": 30}
            next_delivery = date.today() + timedelta(days=intervals.get(frequency, 30))
            await add_subscription(user_id, product_id, product_name, frequency, next_delivery)
            await query.message.reply_text(
                f"✅ *Subscription Active!*\n\n"
                f"📦 {product_name}\n"
                f"🔄 Frequency: {frequency.title()}\n"
                f"📅 Next delivery: {next_delivery.strftime('%b %d, %Y')}\n\n"
                f"You can manage subscriptions anytime.",
                parse_mode="Markdown",
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Subscription setup failed: {e}")
            await query.message.reply_text("Sorry, couldn't set up subscription. Try again later.")

    elif data.startswith("proactive:submit"):
        await _handle_proactive_submit(query, user_id)


# ── STEP 1: Show auth card ──
async def _handle_credit_start(query, user_id: int):
    """Show the Connect PayPal auth card."""
    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)

    await query.message.reply_text(
        "Great choice! I'll find the best credit product "
        "personalised for you.\n\n"
        "First, let me securely connect your PayPal account. 🔒",
        parse_mode="Markdown",
    )

    await asyncio.sleep(0.5)

    # Auth card — "Connect with PayPal" opens Mini App login screen
    login_url = f"{WEBAPP_URL}/webapp?mode=login"

    await query.message.reply_text(
        "🔐 *Connect PayPal*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "Sign in with your PayPal account to unlock\n"
        "personalised credit offers.\n\n"
        "🔒 Secure OAuth — we never see your password.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Connect with PayPal", web_app=WebAppInfo(url=login_url))],
        ]),
    )

    # Start background polling for login completion (non-blocking)
    asyncio.create_task(_poll_login(query, user_id))


# ── STEP 2: Post Mini App login — continues flow in bot chat ──
async def _handle_post_login(query, user_id: int):
    """Called after user logs in via Mini App and taps 'Continue in chat'."""
    from bot.services.session import get_session
    session = get_session(user_id)
    name = session.get("name", "User")
    email = session.get("email", "")

    await query.message.reply_text(
        f"✅ *Connected successfully!*\n\n"
        f"👤 {name}\n"
        f"📧 {email}\n"
        f"🏦 PayPal member: 36 months\n"
        f"💳 Credit band: _prime_",
        parse_mode="Markdown",
    )
    await asyncio.sleep(1)
    await _handle_scoring(query, user_id)


# ── STEP 3: Scoring ──
async def _handle_scoring(query, user_id: int):
    """Analyze profile and present offers."""
    from bot.services.session import get_session
    session = get_session(user_id)
    name = session.get("name", "User")

    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text(
        f"🔍 *Analyzing your profile...*\n\n"
        f"Reviewing your PayPal history to find the\n"
        f"best credit products for you.\n\n"
        f"_This will only take a moment..._",
        parse_mode="Markdown",
    )

    await asyncio.sleep(2.5)

    await query.message.reply_text(
        "✅ *Analysis complete!*\n"
        "📊 Offers matched: *3*\n"
        "⏱ Response time: *2.8 seconds*",
        parse_mode="Markdown",
    )
    await asyncio.sleep(1)

    set_state(user_id, FlowState.OFFERS_SHOWN)
    await query.message.reply_text(
        f"🎯 Great news, {name} — we found *3 personalised offers* for you.\n"
        "Tap one to learn more:\n\n" + all_offers_message(),
        parse_mode="Markdown",
        reply_markup=offers_keyboard(),
    )


# ── STEP 4: Show application form after offer selection ──
async def _handle_application_form(query, user_id: int):
    """Show pre-filled form after user selects an offer."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        await query.message.reply_text("Please select an offer first.")
        return

    from bot.services.session import get_session
    session = get_session(user_id)
    name = session.get("name", "User")
    email = session.get("email", "")
    o = CREDIT_OFFERS[offer_idx]

    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(0.5)

    form_url = f"{WEBAPP_URL}/webapp?mode=form&name={name}&email={email}"
    await query.message.reply_text(
        f"📋 *Application for {o['name']}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "19 of 20 fields pre-filled from your PayPal profile:\n\n"
        f"✅ Name: {name}\n"
        f"✅ Email: {email}\n"
        "✅ Phone, Address, DOB, Employer, Income...\n\n"
        "✏️ *Missing: PAN / SSN last 4 digits*\n\n"
        "_Tap below to review and submit:_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Complete Application", web_app=WebAppInfo(url=form_url))],
        ]),
    )

    # Poll for form completion → then show confirm card
    asyncio.create_task(_poll_form_then_confirm(query, user_id))


async def _poll_form_then_confirm(query, user_id: int):
    """Poll for form completion, then show confirm + submit."""
    import httpx
    import logging
    logger = logging.getLogger(__name__)

    for _ in range(60):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/form-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    await query.message.reply_text(
                        "✅ *Application form complete!* All 20 fields confirmed.",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(0.5)
                    await _handle_confirm(query, user_id)
                    return
        except Exception as e:
            logger.debug(f"Form poll error: {e}")


# ── STEP 5: Confirm application ──
async def _handle_confirm(query, user_id: int):
    """Show application confirmation card."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        await query.message.reply_text("Please select an offer first.")
        return

    from bot.services.session import get_session
    name = get_session(user_id).get("name", "User")

    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(0.8)

    await query.message.reply_text(
        "✨ Here's your application summary. Review and tap Submit:\n\n" +
        confirm_message(offer_idx, name),
        parse_mode="Markdown",
        reply_markup=confirm_keyboard(),
    )
    set_state(user_id, FlowState.CONFIRMED)


# ── STEP 5: Submit + Approve ──
async def _handle_submit(query, user_id: int):
    """Process application submission."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        await query.message.reply_text("Please select an offer first.")
        return

    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text("⏳ _Processing your application..._", parse_mode="Markdown")
    await asyncio.sleep(2.5)

    o = CREDIT_OFFERS[offer_idx]
    set_state(user_id, FlowState.APPROVED)

    from bot.services.session import get_session
    user_name = get_session(user_id).get("name", "there")

    await query.message.reply_text(
        f"🎊 *Approved, {user_name}!*\n\n"
        f"Your *{o['name']}* is active.\n\n"
        f"💳 Credit Limit: *{o['amount']}*\n"
        f"⏱ Decision Time: *3.1 seconds*\n"
        f"📋 Status: _Active_\n\n"
        f"📲 All done inside Telegram — no app downloads, no redirects. "
        f"That's Agentic Commerce.\n\n"
        f"What would you like to do next?",
        parse_mode="Markdown",
        reply_markup=post_approval_keyboard(),
    )


async def _handle_tell_more(query, user_id: int):
    """Show more details about the selected offer."""
    offer_idx = get_selected_offer(user_id)
    if offer_idx is None:
        return
    o = CREDIT_OFFERS[offer_idx]

    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)

    await query.message.reply_text(
        f"Here's what to know about *{o['name']}*:\n\n"
        f"✅ *Instant decision* — know in under 4 seconds\n"
        f"🔒 *No hard credit pull* to check eligibility\n"
        f"📱 *Digital-first* — manage entirely in PayPal\n"
        f"🛡 *Buyer Protection* included on all purchases\n"
        f"💸 *{o['detail']}*\n\n"
        f"Ready to proceed?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, apply now", callback_data="action:apply_now")],
            [InlineKeyboardButton("← See other offers", callback_data="action:back_offers")],
        ]),
    )


async def _handle_card_action(query, action: str):
    msgs = {
        "freeze": "🧊 *Card Frozen*\n\nYour card has been temporarily frozen. No transactions will be processed.\n\nTap /menu to unfreeze or manage your card.",
        "replace": "🔄 *Replacement Requested*\n\nA new card will arrive in 3-5 business days.\nYour current card remains active until the new one is activated.",
        "report": "⚠️ *Report Filed*\n\nWe've flagged your card for review. Our fraud team will contact you within 24 hours.",
        "pin": "🔑 *PIN Change*\n\nA PIN change link has been sent to your registered email.\nThe link expires in 15 minutes.",
    }
    await query.message.reply_text(
        msgs.get(action, "Action completed."),
        parse_mode="Markdown",
    )


async def _handle_support(query, action: str):
    messages = {
        "call": "📞 *Call PayPal*\n\n1-888-221-1161\nMon–Fri 6am–6pm PT",
        "chat": "💬 *Live Chat*\n\nVisit: paypal.com/us/smarthelp/home",
        "dispute": "⚠️ *Dispute a Charge*\n\n1. Go to Activity\n2. Find the transaction\n3. Tap 'Report a Problem'",
        "lost": "🔒 *Lost Card*\n\nYour card has been frozen for safety.\nA replacement will arrive in 3-5 business days.",
    }
    await query.message.reply_text(
        messages.get(action, "Contact support at 1-888-221-1161"),
        parse_mode="Markdown",
    )


def _offer_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, apply now", callback_data="action:apply_now")],
        [InlineKeyboardButton("ℹ️ Tell me more", callback_data="action:tell_more")],
        [InlineKeyboardButton("← See other offers", callback_data="action:back_offers")],
    ])


def _post_balance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 View Statement", callback_data="action:statement")],
        [InlineKeyboardButton("🃏 Manage Card", callback_data="action:card")],
    ])


def _card_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧊 Freeze", callback_data="card:freeze"),
            InlineKeyboardButton("🔄 Replace", callback_data="card:replace"),
        ],
        [
            InlineKeyboardButton("⚠️ Report", callback_data="card:report"),
            InlineKeyboardButton("🔑 PIN", callback_data="card:pin"),
        ],
    ])


async def _handle_proactive_offer(query, user_id: int, pattern: str):
    """Show a targeted product card based on the transaction pattern."""
    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)

    offers = {
        "travel": {
            "name": "Venmo Visa Signature Credit Card",
            "limit": "Based on creditworthiness",
            "details": (
                "✈️ *Venmo Visa Signature Credit Card*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 *Auto-detected top category rewards:*\n"
                "✈️ Travel (your top): *3% cashback*\n"
                "🍽 Second category: *2% cashback*\n"
                "🛍 Everything else: *1% cashback*\n\n"
                "🏦 Annual Fee: *$0*\n"
                "📱 Apple Pay, Google Pay, Samsung Pay\n"
                "🪙 Auto-purchase crypto with cashback\n"
                "🔒 Visa Signature benefits included\n\n"
                "No categories to track — your top spending\n"
                "category is detected *automatically* each month.\n\n"
                "Want to apply? I can pre-fill 90% of the form."
            ),
        },
        "dining": {
            "name": "Venmo Visa Signature Credit Card",
            "limit": "Based on creditworthiness",
            "details": (
                "🍽 *Venmo Visa Signature Credit Card*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 *Auto-detected top category rewards:*\n"
                "🍽 Dining (your top): *3% cashback*\n"
                "🛒 Second category: *2% cashback*\n"
                "🛍 Everything else: *1% cashback*\n\n"
                "🏦 Annual Fee: *$0*\n"
                "📱 Digital wallet compatible\n"
                "🔒 Zero liability for unauthorized use\n\n"
                "Covers restaurants, carry-out, delivery,\n"
                "bars, and coffee shops — *automatically*.\n\n"
                "Want to apply? I can pre-fill 90% of the form."
            ),
        },
        "groceries": {
            "name": "PayPal Debit Mastercard",
            "limit": "PayPal Balance",
            "details": (
                "🛒 *PayPal Debit Mastercard*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 *Choose your 5% category each month:*\n"
                "🛒 Groceries: *5% cashback* (up to $1,000/mo)\n"
                "⛽ Also available: Fuel, Restaurants, Apparel\n\n"
                "🏦 No monthly fee · No minimum balance\n"
                "🏧 Free ATM at MoneyPass locations\n"
                "📱 Apple Pay, Google Pay, Samsung Pay\n"
                "✅ No credit check required\n\n"
                "Pick groceries as your monthly category and\n"
                "earn *5% back on every grocery run*.\n\n"
                "Want to get started?"
            ),
        },
        "electronics": {
            "name": "PayPal Credit Card",
            "limit": "Based on creditworthiness",
            "details": (
                "📱 *PayPal Credit Card*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 *Special Financing:*\n"
                "🎯 *0% APR for 6 months* on purchases $149+\n"
                "🛍 Use everywhere Mastercard is accepted\n\n"
                "🏦 Annual Fee: *$0*\n"
                "🔒 Mastercard ID Theft Protection\n"
                "📱 Instant virtual card on approval\n"
                "🛡 PayPal Buyer Protection\n\n"
                "Perfect for big-ticket electronics —\n"
                "spread the cost *interest-free for 6 months*.\n\n"
                "Want to apply? I can pre-fill 90% of the form."
            ),
        },
        "baby": {
            "name": "PayPal Cashback Mastercard",
            "limit": "Based on creditworthiness",
            "details": (
                "👶 *PayPal Cashback Mastercard*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 *Unlimited cashback:*\n"
                "🛒 PayPal purchases: *3% cashback*\n"
                "🌍 Everything else: *1.5% cashback*\n\n"
                "🏦 Annual Fee: *$0 forever*\n"
                "📱 Apple Pay, Google Pay, Samsung Pay\n"
                "🔒 Mastercard ID Theft Protection\n"
                "👥 Up to 6 authorized users\n\n"
                "Great for family spending — earn *3% back*\n"
                "on baby essentials bought via PayPal checkout,\n"
                "and *1.5% on everything else*.\n\n"
                "Want to apply? I can pre-fill 90% of the form."
            ),
        },
        "school": {
            "name": "Venmo Teen Account",
            "limit": "Parent-funded balance",
            "details": (
                "🎒 *Venmo Teen Account*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "👨‍👩‍👧 *For teens ages 13-17:*\n"
                "💳 Their own Venmo debit card\n"
                "👀 You see every transaction in your app\n"
                "🔒 Set spending limits & freeze card anytime\n"
                "💸 Send them money instantly from your Venmo\n\n"
                "🏦 No monthly fee\n"
                "📱 Works with their own Venmo app\n"
                "✅ No credit check\n\n"
                "Give your teen financial independence\n"
                "with *full parental oversight*.\n\n"
                "Want to set one up?"
            ),
        },
    }

    offer = offers.get(pattern, offers["travel"])

    # Store proactive product in session for the apply flow
    from bot.services.session import get_session
    get_session(user_id)["proactive_product"] = offer

    await query.message.reply_text(
        offer["details"],
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ Apply for {offer['name']}", callback_data=f"proactive:apply:{pattern}")],
            [InlineKeyboardButton("ℹ️ Compare with other cards", callback_data="topic:portfolio")],
            [InlineKeyboardButton("❌ Maybe later", callback_data="proactive:no")],
        ]),
    )


async def _handle_shop_pay(query, user_id: int):
    """Process payment — simulated."""
    from bot.services.session import get_session
    from bot.agents.shopping_agent import clear_cart
    session = get_session(user_id)
    cart = session.get("cart", [])
    name = session.get("name", "User")
    total = sum(i["price"] * i["qty"] for i in cart)

    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text("💳 _Processing payment via PayPal..._", parse_mode="Markdown")
    await asyncio.sleep(2)

    items_summary = ", ".join(f"{i['name']}" for i in cart)
    card_used = "PayPal Cashback Mastercard"

    # Save orders to DB
    for item in cart:
        try:
            from bot.services.database import add_order
            await add_order(user_id, item.get("product_id", ""), item["name"], item["price"], item.get("category", ""), card_used)
        except Exception:
            pass

    clear_cart(user_id)

    await query.message.reply_text(
        f"🎉 *Order Confirmed!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Amount: *${total}*\n"
        f"💳 Paid via: {card_used}\n"
        f"👤 Buyer: {name}\n"
        f"📦 Items: {items_summary}\n"
        f"🚚 Estimated delivery: 3-5 business days\n\n"
        f"Thank you for your purchase! 🛍",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 Shop More", callback_data="shop:back")],
            [InlineKeyboardButton("📋 Main Menu", callback_data="topic:menu_show")],
        ]),
    )

    # Post-purchase intelligence — from DB order data
    await _show_post_purchase_intelligence(query, user_id, card_used)


async def _show_post_purchase_intelligence(query, user_id: int, card_used: str):
    """Post-purchase: card tip + subscription nudge — all from DB data."""
    import logging
    _log = logging.getLogger(__name__)

    # 1. Smart Savings Tip — recommend a better card based on order history
    try:
        from bot.agents.intelligence import post_purchase_card_tip
        tip_data = await post_purchase_card_tip(user_id, card_used)

        if tip_data:
            best_card = tip_data["best_card"]
            savings = tip_data["potential_savings"]
            products = tip_data["products"]

            # Try LLM for a human-readable tip, fallback to structured data
            tip_text = None
            try:
                from bot.services.llm_service import credit_enrichment
                from bot.models.cards import RECOMMENDABLE_CARDS, get_card_by_name
                paid_card = get_card_by_name(card_used) or {}
                paid_rewards = ", ".join(f"{k}: {v}" for k, v in paid_card.get("rewards", {}).items()) if paid_card else card_used
                paid_with_detail = f"{card_used} ({paid_rewards})" if paid_rewards else card_used
                rec_portfolio = [{"card_id": c["id"]} for c in RECOMMENDABLE_CARDS]
                llm_tip = await credit_enrichment(products, rec_portfolio, paid_with=paid_with_detail)
                if llm_tip and len(llm_tip) > 10 and "NONE" not in llm_tip.upper():
                    tip_text = llm_tip
            except Exception:
                pass

            # Fallback: generate tip from structured intelligence data
            if not tip_text:
                card_benefit = best_card.get("special", "") or ", ".join(f"{k}: {v}" for k, v in best_card.get("rewards", {}).items())
                tip_text = f"💡 With *{best_card['name']}*, you could save *${savings:.2f}* on this purchase. {card_benefit}"

            pattern_map = {
                "paypal_credit": "electronics", "venmo_visa": "travel",
                "debit_mc": "groceries", "venmo_teen": "school",
            }
            pattern = pattern_map.get(best_card["id"], "travel")
            buttons = [
                [InlineKeyboardButton(f"✅ Apply for {best_card['name']}", callback_data=f"proactive:apply:{pattern}")],
                [InlineKeyboardButton("🛍 Continue Shopping", callback_data="shop:back")],
            ]
            await query.message.reply_text(
                f"*Smart Savings Tip*\n\n{tip_text}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            _log.info(f"Post-purchase tip shown: {best_card['name']} saves ${savings}")
    except Exception as e:
        _log.error(f"Post-purchase card tip failed: {e}")

    # 2. Subscription nudge — if user bought this product before
    try:
        from bot.agents.intelligence import detect_subscription_candidates
        candidates = await detect_subscription_candidates(user_id)

        if candidates:
            top = candidates[0]
            if top["times_bought"] >= 2:
                await query.message.reply_text(
                    f"🔄 *Subscribe & Save*\n\n"
                    f"You've bought *{top['product_name']}* {top['times_bought']} times.\n"
                    f"Set up *{top['suggested_frequency']}* auto-delivery and never run out!\n\n"
                    f"💰 ${top['price']} per delivery",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            f"✅ Subscribe {top['suggested_frequency'].title()}",
                            callback_data=f"subscribe:setup:{top['product_id']}:{top['suggested_frequency']}"
                        )],
                        [InlineKeyboardButton("❌ No thanks", callback_data="shop:back")],
                    ]),
                )
                _log.info(f"Subscription nudge: {top['product_name']} x{top['times_bought']}")
    except Exception as e:
        _log.error(f"Subscription detection failed: {e}")


async def _poll_checkout_complete(query, user_id: int):
    """Poll for checkout completion from Mini App."""
    import httpx
    for _ in range(60):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/checkout-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    from bot.agents.shopping_agent import clear_cart
                    from bot.services.session import get_session
                    session = get_session(user_id)
                    cart = session.get("cart", [])
                    name = session.get("name", "User")
                    total = data.get("total", 0)
                    card_used = data.get("card_used", "PayPal")

                    import logging
                    _log = logging.getLogger(__name__)
                    _log.info(f"Checkout complete: user={user_id}, total={total}, card={card_used}, cart_items={len(cart)}")

                    # Save orders to DB — from session cart or DB cart
                    order_items = cart
                    if not order_items:
                        # Session cart empty (Mini App flow) — try DB cart
                        try:
                            from bot.services.database import get_cart as db_get_cart
                            order_items = await db_get_cart(user_id)
                            _log.info(f"Session cart empty, DB cart has {len(order_items)} items")
                        except Exception:
                            pass

                    if not order_items and total:
                        # Both empty — save a generic order from checkout data
                        order_items = [{"product_id": "", "name": "Purchase", "price": float(total), "category": "general"}]
                        _log.info(f"No cart data, saving generic order for ${total}")

                    for item in order_items:
                        try:
                            from bot.services.database import add_order
                            price = float(item.get("price", 0))
                            await add_order(user_id, item.get("product_id", ""), item.get("product_name", item.get("name", "Item")), price, item.get("category", "general"), card_used)
                        except Exception as e:
                            _log.error(f"Failed to save order: {e}")

                    clear_cart(user_id)

                    await query.message.reply_text(
                        f"🎉 *Order Confirmed!*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"💰 Amount: *${total}*\n"
                        f"💳 Paid via: {card_used}\n"
                        f"👤 Buyer: {name}\n"
                        f"🚚 Estimated delivery: 3-5 business days\n\n"
                        f"Thank you for your purchase! 🛍",
                        parse_mode="Markdown",
                    )

                    # Post-purchase intelligence — from DB order data
                    await _show_post_purchase_intelligence(query, user_id, card_used)

                    return
        except Exception:
            pass


async def _handle_shop_checkout(query, user_id: int):
    """Handle shopping cart checkout — PayPal connect + confirm."""
    from bot.services.session import get_session
    session = get_session(user_id)
    cart = session.get("cart", [])

    if not cart:
        await query.message.reply_text("🛒 Your cart is empty!")
        return

    total = sum(i["price"] * i["qty"] for i in cart)
    name = session.get("name", "")

    if not name:
        # Need to connect PayPal first
        login_url = f"{WEBAPP_URL}/webapp?mode=login"
        await query.message.reply_text(
            "💳 *Checkout via PayPal*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Cart total: *${total}*\n\n"
            "Connect your PayPal account to complete the purchase.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Connect with PayPal", web_app=WebAppInfo(url=login_url))],
            ]),
        )
        # After login, show checkout confirmation
        asyncio.create_task(_poll_login_then_checkout(query, user_id))
    else:
        # Already connected — show order summary + confirm
        await _show_checkout_confirm(query, user_id)


async def _show_checkout_confirm(query, user_id: int):
    """Show checkout confirmation with order summary."""
    from bot.services.session import get_session
    session = get_session(user_id)
    cart = session.get("cart", [])
    name = session.get("name", "User")
    total = sum(i["price"] * i["qty"] for i in cart)

    lines = [
        "✅ *Order Summary*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for item in cart:
        lines.append(f"{item['icon']} {item['name']} × {item['qty']} — *${item['price'] * item['qty']}*")
    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 Total: *${total}*")
    lines.append(f"👤 Buyer: {name}")
    lines.append(f"💳 Payment: PayPal")

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Pay with PayPal", callback_data="shop:pay")],
            [InlineKeyboardButton("← Back to Cart", callback_data="shop:showcart")],
        ]),
    )


async def _poll_login_then_checkout(query, user_id: int):
    """Poll for login completion, then show checkout."""
    import httpx
    for _ in range(30):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/login-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    from bot.services.session import get_session
                    session = get_session(user_id)
                    session["name"] = data["name"]
                    session["email"] = data["email"]

                    await query.message.reply_text(
                        f"✅ *Connected as {data['name']}*",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(0.5)

                    # Open Mini App checkout
                    import urllib.parse
                    cart = session.get("cart", [])
                    total = sum(i["price"] * i["qty"] for i in cart)
                    items_param = urllib.parse.quote(",".join(f"{i['icon']}{i['name']}|{i['price']}|{i['qty']}" for i in cart[:5]))
                    checkout_url = f"{WEBAPP_URL}/webapp?mode=checkout&uid={user_id}&total={total}&name={urllib.parse.quote(data['name'])}&items={items_param}"
                    await query.message.reply_text(
                        f"💳 *Checkout — ${total}*\n\nTap below to review and pay:",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("💳 Pay with PayPal", web_app=WebAppInfo(url=checkout_url))],
                        ]),
                    )
                    asyncio.create_task(_poll_checkout_complete(query, user_id))
                    return
        except Exception:
            pass


async def _handle_proactive_submit(query, user_id: int):
    """Submit application for the proactive product."""
    from bot.services.session import get_session
    session = get_session(user_id)
    product = session.get("proactive_product", {})
    product_name = product.get("name", "PayPal Credit Card")
    product_limit = product.get("limit", "$5,000")
    name = session.get("name", "User")

    await query.message.chat.send_action(ChatAction.TYPING)
    await query.message.reply_text("⏳ _Processing your application..._", parse_mode="Markdown")
    await asyncio.sleep(2.5)

    set_state(user_id, FlowState.APPROVED)
    await query.message.reply_text(
        f"🎊 *Approved, {name}!*\n\n"
        f"Your *{product_name}* is active.\n\n"
        f"💳 Credit Limit: *{product_limit}*\n"
        f"⏱ Decision Time: *3.1 seconds*\n"
        f"📋 Status: _Active_\n\n"
        f"📲 All done inside Telegram — no app downloads, no redirects. "
        f"That's Agentic Commerce.\n\n"
        f"What would you like to do next?",
        parse_mode="Markdown",
        reply_markup=post_approval_keyboard(),
    )


async def _handle_proactive_apply(query, user_id: int, pattern: str):
    """Apply for the specific proactive product — skip generic offers."""
    from bot.services.session import get_session
    session = get_session(user_id)
    product = session.get("proactive_product", {})
    product_name = product.get("name", "PayPal Credit Card")

    # Mark this as a proactive application flow
    session["proactive_apply"] = True

    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(0.5)

    await query.message.reply_text(
        f"Great choice! Let's get you the *{product_name}*.\n\n"
        "First, let me securely connect your PayPal account. 🔒",
        parse_mode="Markdown",
    )
    await asyncio.sleep(0.5)

    login_url = f"{WEBAPP_URL}/webapp?mode=login"
    await query.message.reply_text(
        "🔐 *Connect PayPal*\n"
        "━━━━━━━━━━━━━━━━━\n"
        "Sign in with your PayPal account to\n"
        f"apply for *{product_name}*.\n\n"
        "🔒 Secure OAuth — we never see your password.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Connect with PayPal", web_app=WebAppInfo(url=login_url))],
        ]),
    )

    # Poll for login → then skip offers, go straight to form → confirm
    asyncio.create_task(_poll_login_proactive(query, user_id, pattern))


async def _poll_login_proactive(query, user_id: int, pattern: str):
    """Poll for login, then go straight to form → confirm for the proactive product."""
    import httpx

    for _ in range(30):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/login-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    from bot.services.session import get_session
                    session = get_session(user_id)
                    session["name"] = data["name"]
                    session["email"] = data["email"]
                    product = session.get("proactive_product", {})
                    product_name = product.get("name", "PayPal Credit Card")
                    product_limit = product.get("limit", "$5,000")

                    await query.message.reply_text(
                        f"✅ *PayPal account connected!*\n\n"
                        f"👤 *{data['name']}*\n"
                        f"📧 {data['email']}",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(1)

                    # Show form for this specific product
                    form_url = f"{WEBAPP_URL}/webapp?mode=form&name={data['name']}&email={data['email']}"
                    await query.message.reply_text(
                        f"📋 *Application for {product_name}*\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "19 of 20 fields pre-filled from your PayPal profile.\n\n"
                        "✏️ *Missing: PAN / SSN last 4 digits*\n\n"
                        "_Tap below to review and submit:_",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📝 Complete Application", web_app=WebAppInfo(url=form_url))],
                        ]),
                    )

                    # Poll for form → then confirm for this specific product
                    asyncio.create_task(_poll_form_proactive(query, user_id, pattern))
                    return
        except Exception:
            pass


async def _poll_form_proactive(query, user_id: int, pattern: str):
    """Poll for form completion → show confirm for the proactive product."""
    import httpx

    for _ in range(60):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/form-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    from bot.services.session import get_session
                    session = get_session(user_id)
                    product = session.get("proactive_product", {})
                    product_name = product.get("name", "PayPal Credit Card")
                    product_limit = product.get("limit", "$5,000")
                    name = session.get("name", "User")

                    await query.message.reply_text(
                        "✅ *Application form complete!*",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(0.5)

                    # Confirm card for this specific product
                    await query.message.reply_text(
                        f"✅ *Application Ready*\n"
                        f"━━━━━━━━━━━━━━━━━\n"
                        f"Product: *{product_name}*\n"
                        f"Credit Limit: *{product_limit}*\n"
                        f"Applicant: {name}\n"
                        f"Channel: Telegram\n"
                        f"Decision: _Instant · ~3s_\n\n"
                        f"Tap Submit to apply:",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Submit Application", callback_data=f"proactive:submit:{pattern}")],
                        ]),
                    )
                    return
        except Exception:
            pass


async def _handle_portfolio(query):
    """Show credit portfolio analysis."""
    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    await query.message.reply_text(
        "🔍 _Fetching your spend history and card usage..._",
        parse_mode="Markdown",
    )
    await asyncio.sleep(2)
    await query.message.reply_text(
        portfolio_message(),
        parse_mode="Markdown",
        reply_markup=portfolio_keyboard(),
    )


async def _handle_collections(query):
    """Show collections/overdue scenario."""
    await query.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    await query.message.reply_text(
        collections_message(),
        parse_mode="Markdown",
        reply_markup=collections_keyboard(),
    )


async def _poll_login(query, user_id: int):
    """Background task — polls API for Mini App login completion."""
    import httpx
    import logging
    logger = logging.getLogger(__name__)

    for _ in range(30):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/login-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    from bot.services.session import get_session
                    session = get_session(user_id)
                    session["name"] = data["name"]
                    session["email"] = data["email"]

                    await query.message.reply_text(
                        f"✅ *PayPal account connected!*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 *{data['name']}*\n"
                        f"📧 {data['email']}\n"
                        f"🏦 PayPal member: 36 months\n"
                        f"💳 Eligibility: _Pre-qualified_",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(1)

                    # Go straight to scoring → offers
                    await _handle_scoring(query, user_id)
                    return
        except Exception as e:
            logger.debug(f"Login poll error: {e}")
    logger.info(f"Login poll timeout for user {user_id}")


async def _poll_form(query, user_id: int):
    """Background task — polls API for form completion."""
    import httpx
    import logging
    logger = logging.getLogger(__name__)

    for _ in range(60):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{WEBAPP_URL}/api/form-status?telegram_user_id={user_id}")
                data = resp.json()
                if data.get("done"):
                    await query.message.reply_text(
                        "✅ *Application form complete!* All 20 fields confirmed.\n\n"
                        "_Analyzing your profile..._",
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(1)
                    await _handle_scoring(query, user_id)
                    return
        except Exception as e:
            logger.debug(f"Form poll error: {e}")
    logger.info(f"Form poll timeout for user {user_id}")


def _card_manage_message(name: str = "User") -> str:
    return (
        "🃏 *Card Management*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "💳 *Virtual Card*\n"
        "Card: `•••• •••• •••• 4821`\n"
        f"Holder: {name.upper()}\n"
        "Expiry: 09/28\n"
        "Type: PayPal Pay Later\n\n"
        "📊 *Spending Limit*\n"
        "Used: $847.23 of $2,500 (33.9%)\n"
        "▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░ 33.9%\n\n"
        "*Controls:*\n"
        "🌐 Online Purchases: ✅ On\n"
        "✈️ International: ❌ Off\n"
        "📱 Contactless: ✅ On\n"
        "🔔 Spend Alerts: ✅ On"
    )
