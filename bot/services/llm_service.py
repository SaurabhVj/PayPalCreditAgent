"""LLM service — Google Gemini integration for natural conversation."""

import json
import httpx
from bot.config import GEMINI_API_KEY
from bot.services.mock_data import MOCK_USER, MOCK_BALANCE, MOCK_TRANSACTIONS, MOCK_REWARDS
from bot.models.offers import CREDIT_OFFERS

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SYSTEM_PROMPT = """You are PayPal Credit Agent, a friendly and professional AI assistant that helps users with PayPal credit products.

You have access to the following user data:
- User: {name}, email: {email}, PayPal member for {tenure} months, credit band: {band}
- Monthly spend: ${spend}
- Current balance: {balance}, available credit: {available}, due date: {due}
- Rewards: {cashback} cashback YTD, {points} points, {tier} tier

Available credit products:
1. PayPal Pay Later — $2,500 limit, 0% APR for 6 months, no annual fee (Best Match, 96% score)
2. PayPal Cashback Mastercard — $5,000 limit, 3% cashback on PayPal purchases (Premium, 84% score)
3. PayPal Credit Line — $1,200 limit, 19.99% APR, good for building credit (Starter, 71% score)

Guidelines:
- Be concise and helpful (2-3 sentences max)
- Recommend products based on what the user asks about
- If they ask about travel/rewards → recommend Miles+ or Cashback
- If they ask about building credit → recommend Credit Line
- If they ask about balance/payments/transactions → give their account info
- Use emojis sparingly for warmth
- Never make up data — use only the information provided above
- If unsure, suggest they explore the menu options
""".format(
    name=MOCK_USER["name"], email=MOCK_USER["email"],
    tenure=MOCK_USER["tenure_months"], band=MOCK_USER["credit_band"],
    spend=f"{MOCK_USER['monthly_spend']:,}",
    balance=MOCK_BALANCE["current_balance"], available=MOCK_BALANCE["available_credit"],
    due=MOCK_BALANCE["due_date"],
    cashback=MOCK_REWARDS["total_cashback"], points=f"{MOCK_REWARDS['points']:,}",
    tier=MOCK_REWARDS["tier"],
)


async def ask_llm(user_message: str, conversation_history: list[dict] | None = None) -> str:
    """Send a message to Gemini and get a response."""
    if not GEMINI_API_KEY:
        return None  # Fallback to regex intent detection

    contents = []

    # Add system prompt as first user message
    contents.append({"role": "user", "parts": [{"text": SYSTEM_PROMPT}]})
    contents.append({"role": "model", "parts": [{"text": "Understood. I'm PayPal Credit Agent, ready to help with credit products, balance, rewards, and more."}]})

    # Add conversation history if available
    if conversation_history:
        for msg in conversation_history[-6:]:  # Last 6 messages for context
            contents.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["content"]}]
            })

    # Add current message
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 300,
                    }
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                return None  # Fallback to regex
    except Exception:
        return None  # Fallback to regex
