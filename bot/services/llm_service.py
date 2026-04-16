"""LLM service — Gemini integration with workflow routing."""

import json
import logging
import httpx
from bot.config import GEMINI_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are PayPal Assistant, a friendly AI that helps users with BOTH shopping and credit products on Telegram.

## YOUR CAPABILITIES
You can trigger workflows using action tags. ONLY use an action tag when the user's intent CLEARLY matches. When in doubt, just reply naturally or show the menu.

### Shopping:
- **Product Search**: User wants to buy/find a product → [ACTION:SHOP:search query here]
  Examples: "I want Nike Jordan" → [ACTION:SHOP:nike jordan], "find headphones" → [ACTION:SHOP:headphones]
- **View Cart**: "show my cart", "what's in my cart" → [ACTION:CART]

### Credit:
- **Apply for Credit**: User explicitly wants a credit card → [ACTION:CREDIT]
- **Check Balance**: "what's my balance", "how much do I owe" → [ACTION:BALANCE]
- **Credit Portfolio**: "show my cards", "portfolio analysis" → [ACTION:PORTFOLIO]
- **Collections**: "overdue payment", "can't pay" → [ACTION:COLLECTIONS]
- **View Rewards**: "my rewards", "cashback earned" → [ACTION:REWARDS]

### General:
- **Show Menu**: Greetings (hi, hello), "what can you do?", "help", "menu" → [ACTION:MENU]

## CRITICAL RULES
1. For greetings like "hi", "hello", "hey" → ALWAYS use [ACTION:MENU]. Do NOT show credit options.
2. For "what can you do?" or "help" → use [ACTION:MENU]
3. Action tags must NEVER be visible to the user. Put them on a separate line at the very end.
4. Do NOT include the raw action tag text in your friendly message.
5. If user's intent is unclear, ask a clarifying question — do NOT default to credit.
6. For shopping queries, ALWAYS extract the product name into the action tag.
7. NEVER combine a clarifying question with an action tag. Either ask a question (no action tag) OR trigger an action (no question). Never both.
8. "Show more", "more options", "any other" → search again with a broader query using [ACTION:SHOP:broader term]. Do NOT ask what they want — they already told you.
9. If user already searched for something and asks follow-up like "show more", "other options", "anything else" → use the SAME search context from conversation history to search again or broaden the query. Do NOT ask them to repeat.

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


def build_prompt(user_name: str = "", user_email: str = "", proactive_context: dict | None = None) -> str:
    """Build system prompt with dynamic user + proactive context appended."""
    prompt = SYSTEM_PROMPT

    # Add dynamic user context
    if user_name:
        prompt += f"\n\n## CURRENT USER\nName: {user_name}\nEmail: {user_email}\nAddress the user by their first name.\n"

    # Add proactive trigger context if present
    if proactive_context:
        prompt += (
            f"\n\n## RECENT PROACTIVE TRIGGER\n"
            f"The bot detected a transaction and proactively messaged the user.\n"
            f"Merchant: {proactive_context.get('merchant', 'Unknown')}\n"
            f"Amount: ${proactive_context.get('amount', 0)}\n"
            f"Category: {proactive_context.get('category', 'unknown')}\n"
            f"Product offered: {proactive_context.get('product', 'Unknown')}\n\n"
            f"If the user asks 'how did you know' or 'how do you have my data':\n"
            f"- Explain that you detected the transaction pattern on their PayPal account\n"
            f"- Reassure them their data is private and secure\n"
            f"- Mention the specific merchant and amount to show transparency\n"
        )

    return prompt


async def ask_llm(user_message: str, conversation_history: list[dict] | None = None,
                  user_name: str = "", user_email: str = "",
                  proactive_context: dict | None = None) -> str:
    """Send a message to Gemini and get a response."""
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        return None

    prompt = build_prompt(user_name, user_email, proactive_context)

    # Build messages in OpenAI format (used by Groq)
    messages = [
        {"role": "system", "content": prompt},
    ]
    if conversation_history:
        for msg in conversation_history[-15:]:
            messages.append({
                "role": msg["role"] if msg["role"] == "user" else "assistant",
                "content": msg["content"],
            })
    messages.append({"role": "user", "content": user_message})

    # Try Groq first (faster, higher quota)
    if GROQ_API_KEY:
        result = await _call_groq(messages)
        if result:
            return result

    # Fallback to Gemini
    if GEMINI_API_KEY:
        result = await _call_gemini(messages, prompt, user_message, conversation_history)
        if result:
            return result

    logger.warning("All LLM providers failed")
    return None


async def _call_groq(messages: list[dict]) -> str | None:
    """Call Groq API (OpenAI-compatible)."""
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    for model in models:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"]
                    logger.info(f"Groq ({model}) responded successfully")
                    return text.strip()
                else:
                    logger.warning(f"Groq ({model}) returned {resp.status_code}: {resp.text[:200]}")
                    continue
        except Exception as e:
            logger.error(f"Groq ({model}) error: {e}")
            continue
    return None


async def _call_gemini(messages: list[dict], prompt: str, user_message: str,
                       conversation_history: list[dict] | None) -> str | None:
    """Fallback to Gemini API."""
    contents = [
        {"role": "user", "parts": [{"text": prompt}]},
        {"role": "model", "parts": [{"text": "Understood. I'm PayPal Credit Agent ready to help."}]},
    ]
    if conversation_history:
        for msg in conversation_history[-15:]:
            contents.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["content"]}],
            })
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json={"contents": contents, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}})
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info(f"Gemini ({model}) responded successfully")
                    return text.strip()
                else:
                    continue
        except Exception:
            continue
    return None


def parse_action(response: str) -> tuple[str | None, str, str]:
    """Extract action tag from LLM response. Returns (action, clean_message, extra_data)."""
    if not response:
        return None, "", ""

    import re
    action = None
    clean = response
    extra = ""

    # Check for SHOP with query: [ACTION:SHOP:nike jordan]
    shop_match = re.search(r'\[ACTION:SHOP:([^\]]+)\]', response)
    if shop_match:
        action = "shop"
        extra = shop_match.group(1).strip()
        clean = response.replace(shop_match.group(0), "").strip()
    else:
        for tag in ["[ACTION:CREDIT]", "[ACTION:BALANCE]", "[ACTION:PORTFOLIO]",
                    "[ACTION:COLLECTIONS]", "[ACTION:REWARDS]", "[ACTION:MENU]",
                    "[ACTION:CART]"]:
            if tag in response:
                action = tag.replace("[ACTION:", "").replace("]", "").lower()
                clean = response.replace(tag, "").strip()
                break

    # Aggressively clean any remaining action tag artifacts
    clean = re.sub(r'\[ACTION:[^\]]*\]', '', clean).strip()
    # Remove "action:", "Action:", etc. that LLM might leak
    clean = re.sub(r'(?i)\baction:\s*\w+', '', clean).strip()
    # Remove empty lines left over
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()

    return action, clean, extra
