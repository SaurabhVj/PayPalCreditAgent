"""Message formatting helpers."""

from bot.models.offers import CREDIT_OFFERS
from bot.services.mock_data import MOCK_USER, MOCK_BALANCE, MOCK_TRANSACTIONS, MOCK_REWARDS


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
        f"💳 Credit band: _{u['credit_band']}_\n"
        f"💰 Avg monthly spend: ${u['monthly_spend']:,}\n\n"
        f"_Running NBA model..._"
    )
