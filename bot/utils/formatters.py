"""Message formatting helpers."""

from bot.models.offers import CREDIT_OFFERS
from bot.services.mock_data import (
    MOCK_USER, MOCK_BALANCE, MOCK_TRANSACTIONS, MOCK_REWARDS,
    MOCK_PORTFOLIO, MOCK_COLLECTIONS,
)


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


def balance_message() -> str:
    b = MOCK_BALANCE
    return (
        f"💰 *Account Balance*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Current Balance: *{b['current_balance']}*\n"
        f"Available Credit: *{b['available_credit']}*\n"
        f"Credit Limit: {b['credit_limit']}\n"
        f"Due Date: {b['due_date']}\n"
        f"Min Payment: {b['min_payment']}\n"
        f"Utilization: {b['utilization']}"
    )


def statement_message() -> str:
    lines = [
        f"📋 *Recent Transactions*\n"
        f"━━━━━━━━━━━━━━━━━\n"
    ]
    for t in MOCK_TRANSACTIONS:
        cr = " 💚" if t.get("credit") else ""
        lines.append(f"{t['icon']} *{t['name']}*  {t['amount']}{cr}")
        lines.append(f"   _{t['category']}_ · {t['date']}\n")
    return "\n".join(lines)


def rewards_message() -> str:
    r = MOCK_REWARDS
    return (
        f"🎁 *Your Rewards*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Cash Back YTD: *{r['total_cashback']}*\n"
        f"Points Balance: *{r['points']:,}*\n"
        f"Tier: {r['tier']}\n"
        f"Next Milestone: _{r['next_milestone']}_"
    )


def scoring_message() -> str:
    u = MOCK_USER
    return (
        f"🧠 *Analyzing your profile...*\n\n"
        f"👤 {u['name']}\n"
        f"📧 {u['email']}\n"
        f"📅 PayPal member: {u['tenure_months']} months\n"
        f"💳 Eligibility: _Pre-qualified_\n"
        f"💰 Avg monthly spend: ${u['monthly_spend']:,}\n\n"
        f"_This will only take a moment..._"
    )


def portfolio_message() -> str:
    p = MOCK_PORTFOLIO
    lines = [
        f"📊 *Your Credit Portfolio*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 Total Credit: *{p['total_credit']}*\n"
        f"💰 Total Balance: *{p['total_balance']}*\n"
        f"📊 Utilization: *{p['utilization']}* ✅ Healthy\n"
        f"🎁 Rewards YTD: *{p['rewards_ytd']}*\n"
    ]
    for card in p["cards"]:
        lines.append(
            f"\n*{card['name']}* ({card['number']})\n"
            f"  Limit: {card['limit']} · Balance: {card['balance']}\n"
            f"  Available: {card['available']} · Util: {card['utilization']}\n"
            f"  Rewards: {card['rewards']}\n"
            f"  💡 _{card['nudge']}_"
        )
    return "\n".join(lines)


def portfolio_optimize_message() -> str:
    return (
        "🔄 *Spend Optimization Tips*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ *Groceries*: Switch from Miles+ (1x) to Everyday Cash (2%)\n"
        "   → Save *$86/yr* more in cashback\n\n"
        "2️⃣ *Travel*: Keep using Miles+ (3x miles)\n"
        "   → You're earning optimally here ✅\n\n"
        "3️⃣ *Dining*: Miles+ earns 2x, Everyday Cash earns 2%\n"
        "   → Miles+ is slightly better if you value miles\n\n"
        "4️⃣ *Online Shopping*: Use Everyday Cash (2% flat)\n"
        "   → Miles+ only earns 1x here\n\n"
        "💡 _Overall you could earn *$86 more per year* by using the right card for each category._"
    )


def portfolio_compare_message() -> str:
    return (
        "🔀 *Card Comparison*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Miles+* vs *Everyday Cash*\n\n"
        "✈️ Travel:    Miles+ *3x* vs Cash *2%*  → Miles+ wins\n"
        "🍽 Dining:    Miles+ *2x* vs Cash *2%*  → Tie\n"
        "🛒 Groceries: Miles+ *1x* vs Cash *2%*  → Cash wins\n"
        "🛍 Shopping:  Miles+ *1x* vs Cash *2%*  → Cash wins\n"
        "🏦 Annual fee: Miles+ *$99* vs Cash *$0*\n\n"
        "📊 *Based on your spend:*\n"
        "  Miles+ projected: *$412/yr* in rewards\n"
        "  Everyday Cash projected: *$286/yr* in cashback\n\n"
        "💡 _Use Miles+ for travel & dining, Everyday Cash for everything else._"
    )


def collections_message() -> str:
    c = MOCK_COLLECTIONS
    return (
        f"⚖️ *Collections — Case #{c['case_id']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Your account is *{c['days_past_due']} days past due*.\n\n"
        f"💳 Card: {c['card']}\n"
        f"💸 Overdue Amount: *{c['overdue_amount']}*\n"
        f"💵 Minimum Due: *{c['minimum_due']}*\n"
        f"📅 Days Past Due: *{c['days_past_due']}*\n"
        f"⚠️ Hardship: _{c['hardship_flag']}_\n\n"
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
    c = MOCK_COLLECTIONS
    return (
        "🤝 *Three Resolution Paths*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Option A* — {c['options']['A']['detail']}\n\n"
        f"*Option B* — {c['options']['B']['detail']}\n\n"
        f"*Option C* — {c['options']['C']['detail']}\n\n"
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
