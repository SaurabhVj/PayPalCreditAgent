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
            "name": "PayPal Miles+",
            "limit": "$22,000",
            "highlight": "75,000 sign-up miles",
            "details": (
                "✈️ *PayPal Miles+*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 Credit Limit: *$22,000*\n"
                "🎁 Sign-up Bonus: *75,000 miles*\n"
                "✈️ Earn Rate: *3x miles on travel*\n"
                "🍽 Dining: *2x miles*\n"
                "🏦 Annual Fee: *$99* (waived Year 1)\n"
                "💱 FX Fees: *None*\n"
                "🛋 Lounge Access: *Priority Pass included*\n\n"
                "Based on your travel spending, you'd earn\n"
                "approximately *$412/year* in rewards.\n\n"
                "Want to apply? I can pre-fill 90% of the form."
            ),
        },
        "baby": {
            "name": "PayPal Family Rewards",
            "limit": "$30,000",
            "highlight": "5% childcare cashback",
            "details": (
                "👶 *PayPal Family Rewards*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 Credit Limit: *$30,000*\n"
                "🍼 Childcare: *5% cashback* (up to $5,000/mo)\n"
                "🛒 Groceries: *3% cashback* unlimited\n"
                "👶 Baby Stores: *4% at partner retailers*\n"
                "🏦 Annual Fee: *$0* first year\n\n"
                "Based on your family spending patterns,\n"
                "you'd earn approximately *$1,500/year* in cashback.\n\n"
                "Want to apply? I can pre-fill 90% of the form."
            ),
        },
        "dining": {
            "name": "PayPal Cashback Mastercard",
            "limit": "$5,000",
            "highlight": "3% dining cashback",
            "details": (
                "🍽 *PayPal Cashback Mastercard*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💳 Credit Limit: *$5,000*\n"
                "🍽 Dining: *3% cashback*\n"
                "🛒 Everything else: *2% cashback*\n"
                "🏦 Annual Fee: *$0 forever*\n\n"
                "Based on your dining spending,\n"
                "you'd earn approximately *$84/year* in dining cashback\n"
                "plus *$172/year* on other purchases.\n\n"
                "Want to apply? I can pre-fill 90% of the form."
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
