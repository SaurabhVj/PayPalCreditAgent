"""Message formatting helpers — uses real card data from cards.py + DB."""

from bot.models.offers import CREDIT_OFFERS
from bot.models.cards import DEFAULT_PORTFOLIO, PAYPAL_CARDS


def welcome_message() -> str:
    return (
        "👋 *Welcome to PayPal Credit Agent*\n\n"
        "I can help you with credit products, check your balance, "
        "view rewards, and more.\n\n"
        "Choose an option below or just type your question:"
    )


def offer_details(index: int) -> str:
    o = CREDIT_OFFERS[index]
    star = "⭐ " if o["highlight"] else ""
    return (
        f"{star}*{o['name']}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 Credit Limit: *{o['amount']}*\n"
        f"📊 Match Score: *{o['score']}%*\n"
        f"📋 {o['detail']}\n"
        f"🏷 _{o['tag']}_"
    )


def all_offers_message() -> str:
    lines = ["🎯 *Credit Offers for You*\n"]
    for i, o in enumerate(CREDIT_OFFERS):
        star = "⭐ " if o["highlight"] else ""
        lines.append(f"{star}*{o['name']}* — {o['amount']}")
        lines.append(f"   {o['detail']}")
        lines.append(f"   Match: {o['score']}% | _{o['tag']}_\n")
    lines.append("Select an offer below:")
    return "\n".join(lines)


def confirm_message(index: int, name: str = "User") -> str:
    o = CREDIT_OFFERS[index]
    return (
        f"✅ *Application Ready*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Product: *{o['name']}*\n"
        f"Credit Limit: *{o['amount']}*\n"
        f"Applicant: {name}\n"
        f"Channel: Telegram\n"
        f"Decision: _Instant · ~3s_\n\n"
        f"Tap Submit to apply:"
    )


def approval_message(index: int) -> str:
    o = CREDIT_OFFERS[index]
    return (
        f"🎉 *Congratulations!*\n\n"
        f"Your *{o['name']}* has been approved!\n\n"
        f"💳 Credit Limit: *{o['amount']}*\n"
        f"⏱ Decision Time: *3.1 seconds*\n"
        f"📋 Status: _Active_\n\n"
        f"What would you like to do next?"
    )


def balance_message(cards: list[dict] | None = None) -> str:
    """Show balance from user's real card portfolio."""
    if not cards:
        cards = DEFAULT_PORTFOLIO

    total_balance = sum(c.get("default_balance", 0) for c in cards)
    total_limit = sum(c.get("default_limit", 0) for c in cards)
    available = total_limit - total_balance
    utilization = round((total_balance / total_limit * 100), 1) if total_limit else 0

    return (
        f"💰 *Account Balance*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Current Balance: *${total_balance:,.2f}*\n"
        f"Available Credit: *${available:,.2f}*\n"
        f"Credit Limit: ${total_limit:,}\n"
        f"Due Date: Apr 15\n"
        f"Min Payment: $25.00\n"
        f"Utilization: {utilization}%"
    )


def statement_message(orders: list[dict] | None = None) -> str:
    """Show recent transactions from real order history."""
    if not orders:
        # Default transactions when no purchase history
        default_txns = [
            {"icon": "👟", "name": "Nike.com", "category": "Fashion", "amount": "-$129.00", "date": "Apr 1"},
            {"icon": "🍔", "name": "Uber Eats", "category": "Dining", "amount": "-$24.50", "date": "Mar 30"},
            {"icon": "📦", "name": "Amazon", "category": "Shopping", "amount": "-$67.99", "date": "Mar 28"},
            {"icon": "☕", "name": "Starbucks", "category": "Coffee", "amount": "-$8.75", "date": "Mar 27"},
            {"icon": "🎵", "name": "Spotify", "category": "Subscriptions", "amount": "-$9.99", "date": "Mar 25"},
        ]
        lines = [
            f"📋 *Recent Transactions*\n"
            f"━━━━━━━━━━━━━━━━━\n"
        ]
        for t in default_txns:
            lines.append(f"{t['icon']} *{t['name']}*  {t['amount']}")
            lines.append(f"   _{t['category']}_ · {t['date']}\n")
        return "\n".join(lines)

    # Real orders from DB
    lines = [
        f"📋 *Recent Transactions*\n"
        f"━━━━━━━━━━━━━━━━━\n"
    ]
    for o in orders[:8]:
        icon = "🛍"
        cat = o.get("category", "Shopping")
        name = o.get("product_name", "Purchase")
        price = o.get("price", 0)
        date_str = o.get("created_at", "")
        if hasattr(date_str, "strftime"):
            date_str = date_str.strftime("%b %d")
        lines.append(f"{icon} *{name}*  -${price}")
        lines.append(f"   _{cat}_ · {date_str} · 💳 {o.get('card_used', 'PayPal')}\n")
    return "\n".join(lines)


def rewards_message(cards: list[dict] | None = None) -> str:
    """Show rewards from user's real card portfolio."""
    if not cards:
        cards = DEFAULT_PORTFOLIO

    total_cashback = sum(c.get("default_rewards_earned", 0) for c in cards)

    lines = [
        f"🎁 *Your Rewards*\n"
        f"━━━━━━━━━━━━━━━━━\n"
    ]
    for c in cards:
        earned = c.get("default_rewards_earned", 0)
        rewards_desc = ", ".join(f"{k}: {v}" for k, v in c.get("rewards", {}).items())
        lines.append(f"💳 *{c['name']}*")
        lines.append(f"   Earned: *${earned:.2f}* cashback")
        lines.append(f"   Rates: {rewards_desc}\n")

    lines.append(f"━━━━━━━━━━━━━━━━━\n💰 Total YTD: *${total_cashback:.2f}*")
    return "\n".join(lines)


def scoring_message(name: str = "", email: str = "") -> str:
    return (
        f"🧠 *Analyzing your profile...*\n\n"
        f"👤 {name}\n"
        f"📧 {email}\n"
        f"📅 PayPal member: 36 months\n"
        f"💳 Eligibility: _Pre-qualified_\n"
        f"💰 Avg monthly spend: $4,200\n\n"
        f"_This will only take a moment..._"
    )


def portfolio_message(cards: list[dict] | None = None) -> str:
    """Show credit portfolio from real card data."""
    if not cards:
        cards = DEFAULT_PORTFOLIO

    total_limit = sum(c.get("default_limit", 0) for c in cards)
    total_balance = sum(c.get("default_balance", 0) for c in cards)
    total_rewards = sum(c.get("default_rewards_earned", 0) for c in cards)
    utilization = round((total_balance / total_limit * 100), 1) if total_limit else 0
    health = "✅ Healthy" if utilization < 30 else "⚠️ High"

    lines = [
        f"📊 *Your Credit Portfolio*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 Total Credit: *${total_limit:,}*\n"
        f"💰 Total Balance: *${total_balance:,}*\n"
        f"📊 Utilization: *{utilization}%* {health}\n"
        f"🎁 Rewards YTD: *${total_rewards:.2f}*\n"
    ]
    for card in cards:
        balance = card.get("default_balance", 0)
        limit = card.get("default_limit", 0)
        available = limit - balance
        card_util = round((balance / limit * 100), 1) if limit else 0
        rewards_desc = ", ".join(f"{k}: {v}" for k, v in card.get("rewards", {}).items())
        earned = card.get("default_rewards_earned", 0)

        lines.append(
            f"\n*{card['name']}*\n"
            f"  Limit: ${limit:,} · Balance: ${balance:,}\n"
            f"  Available: ${available:,} · Util: {card_util}%\n"
            f"  Rewards: ${earned:.2f} cashback\n"
            f"  Rates: {rewards_desc}"
        )
    return "\n".join(lines)


def portfolio_optimize_message() -> str:
    return (
        "🔄 *Spend Optimization Tips*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ *PayPal purchases*: Use Cashback MC (3%)\n"
        "   → Earns 1.5% more than Everyday Cash\n\n"
        "2️⃣ *Everything else*: Use Everyday Cash (2% flat)\n"
        "   → Beats Cashback MC's 1.5% on non-PayPal\n\n"
        "3️⃣ *Big purchases $149+*: Apply for PayPal Credit\n"
        "   → 0% APR for 6 months — no interest\n\n"
        "4️⃣ *Travel & Dining*: Apply for Venmo Visa (3%)\n"
        "   → Auto-detects your top category\n\n"
        "💡 _Use the right card for each purchase to maximize cashback._"
    )


def portfolio_compare_message() -> str:
    return (
        "🔀 *Card Comparison*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Cashback MC* vs *Everyday Cash*\n\n"
        "🛒 PayPal:    Cashback *3%* vs Cash *2%*  → Cashback wins\n"
        "🏪 Other:     Cashback *1.5%* vs Cash *2%*  → Cash wins\n"
        "💵 Annual fee: Both *$0*\n\n"
        "📊 *Based on typical spend:*\n"
        "  Cashback MC: best for PayPal checkout\n"
        "  Everyday Cash: best for everything else\n\n"
        "💡 _Use both cards strategically — PayPal = Cashback MC, all else = Everyday Cash._"
    )


def collections_message() -> str:
    return (
        f"⚖️ *Collections — Case #C-2024-00391*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Your account is *61 days past due*.\n\n"
        f"💳 Card: PayPal Cashback Mastercard ••••4821\n"
        f"💸 Overdue Amount: *$1,240*\n"
        f"💵 Minimum Due: *$148*\n"
        f"📅 Days Past Due: *61*\n"
        f"⚠️ Hardship: _Possible — spend dropped 60%_\n\n"
        f"I want to help you resolve this — not pressure you.\n"
        f"What would you like to do?"
    )


def collections_hardship_message() -> str:
    return (
        "💛 *Financial Hardship Acknowledged*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Thank you for being upfront. Because you're experiencing\n"
        "genuine hardship, I've unlocked our assistance programme:\n\n"
        "✅ Late fees: *Waived immediately*\n"
        "✅ Interest: *Frozen for 90 days*\n"
        "✅ Credit reporting: *Paused during plan*\n\n"
        "Here are your resolution options:"
    )


def collections_options_message() -> str:
    return (
        "🤝 *Three Resolution Paths*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Option A* — Pay $148 minimum — freeze interest for 90 days\n\n"
        "*Option B* — $415/month · 0% interest · starts next month\n\n"
        "*Option C* — Pay $800 now — 35% reduction\n\n"
        "All options stop further late fees from today.\n"
        "Which works best for you?"
    )


def collections_plan_confirmed(plan: str) -> str:
    plans = {
        "A": "✅ *Minimum Payment Plan*\n\nPayment: $148 today\nInterest: Frozen 90 days\nLate fees: Waived",
        "B": "✅ *Instalment Plan Confirmed*\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n💰 Payment 1: $415 · May 1\n💰 Payment 2: $415 · Jun 1\n💰 Payment 3: $410 · Jul 1\n📊 Interest: 0% during plan\n📋 Credit reporting: Positive\n🚫 Late fees: All waived",
        "C": "✅ *Settlement Confirmed*\n\nAmount: $800 (35% reduction)\nDue: Within 7 days\nAccount: Settled in full after payment",
    }
    msg = plans.get(plan, plans["B"])
    return (
        f"{msg}\n\n"
        "I'll send reminders 3 days before each payment.\n"
        "Reply 'Pay early' any time to pay ahead of schedule.\n"
        "Reply 'I need help' if your situation changes.\n\n"
        "Is there anything else I can help with? 💙"
    )


def dynamic_portfolio_optimize_message(analysis: dict) -> str:
    """Format spend analysis from intelligence.analyze_spend_patterns() into markdown."""
    cats = analysis.get("top_categories", [])
    recs = analysis.get("cards_to_recommend", [])
    total = analysis.get("total_spend", 0)
    order_count = analysis.get("total_orders", 0)

    if not cats:
        return portfolio_optimize_message()  # Fall back to static tips if no order history

    lines = [
        f"🔄 *Spend Optimization — Based on Your Orders*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Analyzed: *{order_count} orders* · *${total:,.2f}* total spend\n"
    ]

    for i, cat in enumerate(cats[:5], 1):
        icon = "✅" if cat["optimal"] else "⚠️"
        lines.append(
            f"\n{icon} *{cat['category'].title()}* — ${cat['spend']:,.2f}\n"
            f"   Using: {cat['card_used']} ({cat['current_rate']})\n"
            f"   Best: {cat['best_card']} ({cat['best_rate']})"
        )
        if cat["potential_savings"] > 0:
            lines.append(f"   💰 Could save: *${cat['potential_savings']:.2f}*")

    if recs:
        lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 *Cards to Consider*\n")
        for r in recs:
            lines.append(
                f"💳 *{r['card_name']}*\n"
                f"   Projected savings: *${r['projected_annual_savings']:.2f}*\n"
                f"   Why: {', '.join(r['reasons'])}"
            )

    return "\n".join(lines)


def subscription_candidates_message(candidates: list[dict]) -> str:
    """Format subscription candidates from intelligence.detect_subscription_candidates()."""
    if not candidates:
        return "📦 No repeat purchases detected yet. Keep shopping and I'll suggest subscriptions when I notice patterns!"

    lines = [
        "🔄 *Subscribe & Save Suggestions*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Based on your purchase history:_\n"
    ]
    for c in candidates:
        lines.append(
            f"📦 *{c['product_name']}*\n"
            f"   Bought {c['times_bought']}x · ~every {c['avg_interval_days']} days\n"
            f"   Suggested: *{c['suggested_frequency'].title()}* · ${c['price']}/delivery\n"
        )
    return "\n".join(lines)
