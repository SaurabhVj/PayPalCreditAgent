"""LLM service — Gemini integration with workflow routing."""

import json
import logging
import httpx
from bot.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are PayPal Credit Agent, a friendly and professional AI assistant on Telegram that helps users with PayPal credit products.

## YOUR CAPABILITIES (4 workflows)
You can trigger these workflows by including an action tag in your response:

1. **Apply for Credit** — Help users apply for credit cards
   Trigger: [ACTION:CREDIT]
   When: User wants to apply, get a card, check offers, needs credit, wants to borrow

2. **Check Balance** — Show account balance and payment info
   Trigger: [ACTION:BALANCE]
   When: User asks about balance, how much they owe, due dates, available credit

3. **Credit Portfolio Analysis** — Multi-card portfolio overview with optimization tips
   Trigger: [ACTION:PORTFOLIO]
   When: User wants to see their cards, portfolio, spend analysis, card comparison, rewards overview

4. **Collections** — Help with overdue payments, hardship, payment plans
   Trigger: [ACTION:COLLECTIONS]
   When: User has overdue payments, can't pay, needs payment plan, financial hardship

5. **Show Menu** — Display the main menu with all options
   Trigger: [ACTION:MENU]
   When: User asks "what can you do?", "show menu", "your functionalities", "help", "options", greets with hi/hello

## IMPORTANT RULES FOR ACTION TAGS
- If the user's message clearly maps to a workflow, include the action tag AND a brief friendly message
- Example: User says "I want a credit card" → respond with "I'd love to help you find the right credit card! Let me start the application process. [ACTION:CREDIT]"
- Example: User says "what can you do?" → respond with "Here's everything I can help you with! [ACTION:MENU]"
- The action tag MUST be on its own line at the end of your message
- If the user is asking a general question (not triggering a workflow), just answer normally WITHOUT any action tag

## USER'S CREDIT PORTFOLIO
The user has 2 active credit cards:

Card 1: PayPal Miles+
- Limit: $22,000 · Balance: $3,240 · Utilization: 14.7%
- Rewards: 42,180 miles · Earn rates: Travel 3x, Dining 2x, Groceries 1x, Other 1x
- Annual fee: $99 (waived Year 1)

Card 2: PayPal Everyday Cash
- Limit: $20,000 · Balance: $580 · Utilization: 2.9%
- Rewards: $114.20 cashback YTD · Earn rates: All categories 2% flat
- Annual fee: $0

Total credit: $42,000 · Total balance: $3,820 · Overall utilization: 9.1%

## SPEND BREAKDOWN (Annual)
- Travel & flights: $4,200/yr
- Dining: $2,800/yr
- Shopping: $3,600/yr
- Other: $1,800/yr
Total: $12,400/yr

## REWARD PROJECTIONS (based on current spend)
- Miles+ projected rewards: ~$412/yr
- Everyday Cash projected rewards: ~$286/yr
- Optimization tip: Use Everyday Cash for groceries & shopping (2% vs 1x on Miles+) → save $86/yr more

## WHAT-IF ANALYSIS
When user asks "what if I spend more on X" or "which card for Y", calculate:
- Miles+ earn: Travel 5%, Dining 3%, Shopping 2%, Other 1%
- Cash earn: All categories 2%
- Compare and recommend the better card for their scenario
- Be specific with dollar amounts

## COLLECTIONS CONTEXT
If user mentions overdue/late payments:
- Current overdue: $1,240 on Miles+ card, 61 days past due
- Options: minimum payment, 3-month instalments, lump sum settlement
- Hardship programme available: waive fees, freeze interest, pause reporting

## CONVERSATION GUIDELINES
- Be warm, concise, and helpful
- For simple questions: 1-3 sentences
- For analysis (what-if, comparisons): be detailed with numbers
- Handle multi-turn follow-ups naturally — remember the conversation context
- Use emojis sparingly for warmth
- Never make up data — use only the information provided above
- If truly unsure what the user wants, ask a clarifying question
"""


async def ask_llm(user_message: str, conversation_history: list[dict] | None = None) -> str:
    """Send a message to Gemini and get a response."""
    if not GEMINI_API_KEY:
        return None

    contents = []
    contents.append({"role": "user", "parts": [{"text": SYSTEM_PROMPT}]})
    contents.append({"role": "model", "parts": [{"text": "Understood. I'm PayPal Credit Agent, ready to help with credit applications, balance checks, portfolio analysis, collections, and more. I'll use action tags to trigger workflows when appropriate."}]})

    if conversation_history:
        for msg in conversation_history[-10:]:
            contents.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["content"]}]
            })

    contents.append({"role": "user", "parts": [{"text": user_message}]})

    models = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash"]

    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    json={
                        "contents": contents,
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 500,
                        }
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info(f"Gemini ({model}) responded successfully")
                    return text.strip()
                else:
                    logger.warning(f"Gemini ({model}) returned {resp.status_code}: {resp.text[:200]}")
                    continue
        except Exception as e:
            logger.error(f"Gemini ({model}) error: {e}")
            continue

    logger.warning("All Gemini models failed, falling back")
    return None


def parse_action(response: str) -> tuple[str | None, str]:
    """Extract action tag from LLM response and return (action, clean_message)."""
    if not response:
        return None, ""

    action = None
    clean = response

    for tag in ["[ACTION:CREDIT]", "[ACTION:BALANCE]", "[ACTION:PORTFOLIO]",
                "[ACTION:COLLECTIONS]", "[ACTION:MENU]"]:
        if tag in response:
            action = tag.replace("[ACTION:", "").replace("]", "").lower()
            clean = response.replace(tag, "").strip()
            break

    return action, clean
