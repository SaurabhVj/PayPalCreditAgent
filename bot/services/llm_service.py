"""LLM service — generic calling layer for orchestrator and agents."""

import json
import logging
import httpx
from bot.config import GROQ_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)


async def classify_intent(message: str, recent_history: list[dict]) -> str:
    """Fast intent classification — returns shopping/credit/menu/general.
    Uses lightweight model for speed."""

    history_text = ""
    if recent_history:
        last_5 = recent_history[-5:]
        history_text = "\n".join(f"{m['role']}: {m['content'][:100]}" for m in last_5)

    prompt = f"""You are an intent classifier for a PayPal shopping and credit assistant.

Given the user's message and recent conversation history, classify the intent into exactly one category:

- "shopping" — user wants to find, buy, browse products, ask about items, show more, what do you have, cart, checkout
- "credit" — user asks about credit cards, balance, payments, portfolio, collections, rewards, apply for card
- "menu" — user greets (hi, hello, hey) or explicitly asks what the bot can do, help, menu
- "general" — general conversation, questions, thanks, compliments, or anything that doesn't fit above

CRITICAL: Look at the conversation history. If the previous messages were about shopping and user says "show more" or "what else" or "any other" or "what do you have" — that is ALWAYS "shopping", never "menu".

Recent conversation:
{history_text}

User message: {message}

Respond with ONLY one word: shopping, credit, menu, or general"""

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 5,
                },
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip().lower()
                # Extract just the category word
                for cat in ["shopping", "credit", "menu", "general"]:
                    if cat in text:
                        logger.info(f"Classified '{message[:30]}' → {cat}")
                        return cat
                logger.warning(f"Classifier returned unexpected: {text}")
                return "general"
    except Exception as e:
        logger.error(f"Classification error: {e}")

    return "general"  # Safe fallback


async def call_agent(system_prompt: str, tools: list[dict], messages: list[dict]) -> dict:
    """Call LLM with agent-specific prompt and tools.
    Returns {"message": str|None, "tool_call": {"name": str, "args": dict}|None}"""

    if GROQ_API_KEY:
        result = await _call_groq(system_prompt, tools, messages)
        if result:
            return result

    if GEMINI_API_KEY:
        result = await _call_gemini_text(system_prompt, messages)
        if result:
            return {"message": result, "tool_call": None}

    return {"message": None, "tool_call": None}


async def general_response(message: str, history: list[dict], user_name: str = "") -> str:
    """Simple conversational response — no tools."""
    system = f"""You are PayPal Assistant, a friendly AI. Respond naturally and concisely.
{"The user's name is " + user_name + "." if user_name else ""}
You help with shopping and credit cards but right now just have a natural conversation."""

    msgs = [{"role": "system", "content": system}]
    if history:
        for m in history[-10:]:
            msgs.append({"role": m["role"] if m["role"] == "user" else "assistant", "content": m["content"]})
    msgs.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant", "messages": msgs, "temperature": 0.7, "max_tokens": 300},
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"General response error: {e}")

    return None


async def rerank_products(query: str, candidates_summary: str) -> list[str]:
    """Ask LLM to pick the most relevant product IDs from candidates."""
    if not GROQ_API_KEY:
        return []

    messages = [
        {"role": "system", "content": (
            "You are a product search relevance engine. "
            "Given a user's search query and a list of candidate products, "
            "return ONLY the IDs of products that are relevant to the query. "
            "Return a JSON array of product IDs, most relevant first. "
            "Maximum 4 products. Be strict — only include products that genuinely match. "
            "For example, 'Nike Jordan shoes' should only return Jordan SHOES, not Nike t-shirts."
        )},
        {"role": "user", "content": f"Query: {query}\n\nCandidates:\n{candidates_summary}\n\nReturn JSON array of matching product IDs:"},
    ]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 100,
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    ids = parsed
                elif isinstance(parsed, dict):
                    ids = parsed.get("ids", parsed.get("product_ids", parsed.get("results", [])))
                else:
                    ids = []
                logger.info(f"Reranked: {len(ids)} products selected")
                return [str(i) for i in ids][:4]
    except Exception as e:
        logger.error(f"Reranking error: {e}")

    return []


async def credit_enrichment(products: list[dict], user_portfolio: list[dict]) -> str | None:
    """Ask Credit Agent to suggest best card usage for these products."""
    if not GROQ_API_KEY or not products:
        return None

    products_text = "\n".join(f"- {p['name']} (${p['price']}, category: {p.get('category', 'general')})" for p in products)
    cards_text = "\n".join(f"- {c.get('card_id', 'unknown')}: balance ${c.get('balance', 0)}, limit ${c.get('credit_limit', 0)}" for c in user_portfolio)

    messages = [
        {"role": "system", "content": (
            "You are a PayPal credit advisor. Given products a user is looking at and their card portfolio, "
            "suggest the BEST card to use and why, in ONE short sentence. "
            "Focus on concrete savings: cashback %, 0% APR, or specific dollar amounts. "
            "If no special benefit applies, return empty string."
        )},
        {"role": "user", "content": f"Products:\n{products_text}\n\nUser's cards:\n{cards_text}"},
    ]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant", "messages": messages, "temperature": 0.3, "max_tokens": 100},
            )
            if resp.status_code == 200:
                tip = resp.json()["choices"][0]["message"]["content"].strip()
                if tip and len(tip) > 5:
                    return f"💡 {tip}"
    except Exception as e:
        logger.error(f"Credit enrichment error: {e}")

    return None


# ── Internal helpers ──

async def _call_groq(system_prompt: str, tools: list[dict], messages: list[dict]) -> dict | None:
    """Call Groq with function calling. Uses 8b (500K tokens/day) with 70b fallback."""
    all_messages = [{"role": "system", "content": system_prompt}] + messages

    for model in ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]:
        body = {
            "model": model,
            "messages": all_messages,
            "temperature": 0.7,
            "max_tokens": 300,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json=body,
                )
                if resp.status_code == 200:
                    msg = resp.json()["choices"][0]["message"]
                    text = msg.get("content") or ""
                    tool_call = None

                    if msg.get("tool_calls"):
                        tc = msg["tool_calls"][0]
                        raw_args = tc["function"].get("arguments", "{}")
                        try:
                            func_args = json.loads(raw_args) if raw_args and raw_args != "null" else {}
                        except (json.JSONDecodeError, TypeError):
                            func_args = {}
                        if not isinstance(func_args, dict):
                            func_args = {}
                        tool_call = {"name": tc["function"]["name"], "args": func_args}

                    logger.info(f"Groq ({model}) agent call OK")
                    return {"message": text.strip() if text else None, "tool_call": tool_call}
                elif resp.status_code == 429:
                    logger.warning(f"Groq ({model}) rate limited, trying next")
                    continue
                else:
                    logger.warning(f"Groq ({model}) {resp.status_code}: {resp.text[:100]}")
                    continue
        except Exception as e:
            logger.error(f"Groq ({model}) error: {e}")
            continue

    return None


async def _call_gemini_text(system_prompt: str, messages: list[dict]) -> str | None:
    """Fallback to Gemini — text only."""
    contents = [
        {"role": "user", "parts": [{"text": system_prompt}]},
        {"role": "model", "parts": [{"text": "Understood."}]},
    ]
    for m in messages[-15:]:
        contents.append({
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        })

    for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json={"contents": contents, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}})
                if resp.status_code == 200:
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            continue
    return None
