"""LLM service — Groq function calling for structured routing + conversation."""

import json
import logging
import re
import httpx
from bot.config import GEMINI_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)

# ── System Prompt (clean — no routing rules, no action tags) ──

SYSTEM_PROMPT = """You are PayPal Assistant, a friendly AI on Telegram that helps users shop for products and manage credit products.

You have tools available — use them when appropriate. For general conversation, just respond naturally without calling any tool.

Key behaviors:
- When user mentions only a brand name (e.g. "Nike", "Apple", "Samsung") without specifying a product → ask what type of product they want. Do NOT call search_products.
- When user asks for a specific product (e.g. "Nike Jordan", "iPhone", "headphones") → call search_products.
- When user says "show more" or "more options" → look at conversation history, find what they searched before, and call search_products with a broader query.
- For greetings (hi, hello, hey) or "what can you do" → call show_menu.
- For general questions about products, credit cards, or anything else → just answer naturally.
"""

PORTFOLIO_CONTEXT = """
## USER'S CREDIT PORTFOLIO
Card 1: PayPal Miles+ — $22K limit, $3,240 balance, 14.7% utilization, 42,180 miles
Card 2: PayPal Everyday Cash — $20K limit, $580 balance, 2.9% utilization, $114 cashback YTD
Total: $42K credit, 9.1% utilization, $698 rewards YTD

## SPEND BREAKDOWN (Annual)
Travel: $4,200 | Dining: $2,800 | Shopping: $3,600 | Other: $1,800
Miles+ earn: Travel 5%, Dining 3%, Shopping 2%, Other 1%
Everyday Cash earn: All categories 2%
"""

# ── Tool Definitions ──

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products to buy. Use when user wants to find or buy a SPECIFIC product (not just a brand name). Examples: 'Nike Jordan', 'headphones', 'baby diapers', 'coffee machine'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Product search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_menu",
            "description": "Show the main menu with shopping and credit options. ONLY use for greetings (hi, hello, hey) or when user explicitly asks 'what can you do', 'help', 'show menu'. NEVER use mid-conversation or after asking a question.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_cart",
            "description": "Show the user's shopping cart contents. Use when user asks about their cart, 'what's in my cart', or wants to checkout.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_for_credit",
            "description": "Start the credit card application flow. Use when user explicitly wants to apply for a credit card or get a new card.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_credit_menu",
            "description": "Show credit services submenu with options: apply for credit, portfolio analysis, rewards, collections. Use when user asks generally about credit cards or financial products.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_balance",
            "description": "Show account balance, available credit, due dates, and payment info.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_portfolio",
            "description": "Show credit card portfolio analysis with multi-card overview and spend optimization tips.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_collections",
            "description": "Show collections and overdue payment resolution options. Use when user mentions overdue payments, can't pay, or financial hardship.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_rewards",
            "description": "Show rewards, cashback earned, points balance, and tier status.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


def build_prompt(user_name: str = "", user_email: str = "", proactive_context: dict | None = None) -> str:
    prompt = SYSTEM_PROMPT + PORTFOLIO_CONTEXT

    if user_name:
        prompt += f"\n\n## CURRENT USER\nName: {user_name}\nEmail: {user_email}\nAddress the user by their first name.\n"

    if proactive_context:
        prompt += (
            f"\n\n## RECENT PROACTIVE TRIGGER\n"
            f"Merchant: {proactive_context.get('merchant', 'Unknown')}\n"
            f"Amount: ${proactive_context.get('amount', 0)}\n"
            f"Category: {proactive_context.get('category', 'unknown')}\n"
            f"Product offered: {proactive_context.get('product', 'Unknown')}\n"
            f"If user asks how you know — explain transaction pattern detection, reassure data is private.\n"
        )

    return prompt


async def ask_llm(user_message: str, conversation_history: list[dict] | None = None,
                  user_name: str = "", user_email: str = "",
                  proactive_context: dict | None = None) -> dict:
    """Send message to LLM. Returns {"message": str, "tool_call": dict|None}."""
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        return {"message": None, "tool_call": None}

    prompt = build_prompt(user_name, user_email, proactive_context)

    messages = [{"role": "system", "content": prompt}]
    if conversation_history:
        for msg in conversation_history[-15:]:
            messages.append({
                "role": msg["role"] if msg["role"] == "user" else "assistant",
                "content": msg["content"],
            })
    messages.append({"role": "user", "content": user_message})

    # Try Groq with function calling
    if GROQ_API_KEY:
        result = await _call_groq_with_tools(messages)
        if result:
            return result

    # Fallback to Gemini (no tool calling — text only)
    if GEMINI_API_KEY:
        text = await _call_gemini(messages, prompt, user_message, conversation_history)
        if text:
            return {"message": text, "tool_call": None}

    return {"message": None, "tool_call": None}


async def _call_groq_with_tools(messages: list[dict]) -> dict | None:
    """Call Groq with function calling support."""
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
                        "tools": TOOLS,
                        "tool_choice": "auto",
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    msg = choice["message"]

                    text = msg.get("content") or ""
                    tool_call = None

                    if msg.get("tool_calls"):
                        tc = msg["tool_calls"][0]
                        func_name = tc["function"]["name"]
                        raw_args = tc["function"].get("arguments", "{}")
                        try:
                            func_args = json.loads(raw_args) if raw_args and raw_args != "null" else {}
                        except (json.JSONDecodeError, TypeError):
                            func_args = {}
                        if not isinstance(func_args, dict):
                            func_args = {}
                        tool_call = {"name": func_name, "args": func_args}

                    logger.info(f"Groq ({model}): text={'yes' if text else 'no'}, tool={tool_call['name'] if tool_call else 'none'}")
                    return {"message": text.strip() if text else None, "tool_call": tool_call}
                else:
                    logger.warning(f"Groq ({model}) returned {resp.status_code}: {resp.text[:200]}")
                    continue
        except Exception as e:
            logger.error(f"Groq ({model}) error: {e}")
            continue
    return None


async def rerank_products(query: str, candidates_summary: str) -> list[str]:
    """Ask LLM to pick the most relevant product IDs from candidates."""
    if not GROQ_API_KEY:
        return []

    messages = [
        {"role": "system", "content": (
            "You are a product search relevance engine. "
            "Given a user's search query and a list of candidate products, "
            "return ONLY the IDs of the products that are relevant to the query. "
            "Return a JSON array of product IDs, most relevant first. "
            "Maximum 4 products. Be strict — only include products that genuinely match what the user is looking for. "
            "For example, if user searches 'Nike Jordan shoes', only return Jordan SHOES, not Nike t-shirts or other Nike products."
        )},
        {"role": "user", "content": f"Query: {query}\n\nCandidates:\n{candidates_summary}\n\nReturn JSON array of matching product IDs:"},
    ]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",  # Fast model for reranking
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 100,
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                # Handle both {"ids": [...]} and direct [...]
                if isinstance(parsed, list):
                    ids = parsed
                elif isinstance(parsed, dict):
                    ids = parsed.get("ids", parsed.get("product_ids", parsed.get("results", [])))
                else:
                    ids = []
                logger.info(f"Reranking: {len(ids)} products selected from candidates")
                return [str(i) for i in ids][:4]
    except Exception as e:
        logger.error(f"Reranking error: {e}")

    return []


async def _call_gemini(messages: list[dict], prompt: str, user_message: str,
                       conversation_history: list[dict] | None) -> str | None:
    """Fallback to Gemini — text only, no tool calling."""
    contents = [
        {"role": "user", "parts": [{"text": prompt}]},
        {"role": "model", "parts": [{"text": "Understood. I'm PayPal Assistant ready to help."}]},
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
                    logger.info(f"Gemini ({model}) responded")
                    return text.strip()
                else:
                    continue
        except Exception:
            continue
    return None
