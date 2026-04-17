"""Credit Agent — handles credit applications, balance, portfolio, collections, rewards."""

import logging
from bot.orchestrator import OrchestratorResult
from bot.services import llm_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a PayPal Credit Specialist assistant. You help users with credit cards, balances, portfolio analysis, collections, and rewards.

You have these tools:
- apply_for_credit: when user wants to apply for a new credit card
- check_balance: when user asks about balance, available credit, due dates
- show_portfolio: when user wants to see their card portfolio, spend analysis, optimization
- show_collections: when user has overdue payments or financial hardship
- show_rewards: when user asks about rewards, cashback earned, points

User's current portfolio:
- PayPal Cashback Mastercard: 3% on PayPal, 1.5% everywhere else, $0 fee
- PayPal Everyday Cash: 2% flat on everything, $0 fee

Available cards to recommend:
- PayPal Credit Card: 0% APR 6 months on $149+
- Venmo Visa Signature: 3% top category (auto-detected), 2% second, 1% rest
- PayPal Debit Mastercard: 5% on chosen monthly category
- Venmo Teen Account: supervised debit for ages 13-17

Additional capabilities:
- analyze_spend: analyze user's actual spending patterns from order history and recommend card optimizations
- analyze_subscriptions: check for repeat purchases that could become auto-delivery subscriptions

Be concise and helpful. If user asks a general credit question, answer directly without calling a tool."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "apply_for_credit",
            "description": "Start credit card application. Use when user explicitly wants to apply for a new card.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_balance",
            "description": "Show account balance, available credit, due dates, payment info.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_portfolio",
            "description": "Show credit card portfolio analysis with spend optimization tips.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_collections",
            "description": "Show collections and overdue payment resolution options.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_rewards",
            "description": "Show rewards, cashback earned, points balance.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_credit_menu",
            "description": "Show credit services submenu. Use when user asks generally about credit options.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_spend",
            "description": "Analyze user's actual spending patterns from order history. Shows which cards to use for which categories, potential savings, and cards to apply for. Use when user asks about optimizing spending, best card usage, or 'how should I use my cards'.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_subscriptions",
            "description": "Check order history for repeat purchases that could become subscriptions. Use when user asks about subscriptions, auto-delivery, or 'what should I subscribe to'.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_subscriptions",
            "description": "Show and manage active subscriptions. Use when user asks to see, modify, cancel, or manage their subscriptions.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


class CreditAgent:
    async def handle(self, message: str, user_id: int,
                     history: list[dict], session: dict) -> OrchestratorResult:
        """Handle credit-related intent."""

        messages = []
        if history:
            for m in history[-10:]:
                messages.append({
                    "role": m["role"] if m["role"] == "user" else "assistant",
                    "content": m["content"],
                })
        messages.append({"role": "user", "content": message})

        result = await llm_service.call_agent(SYSTEM_PROMPT, TOOLS, messages)

        llm_message = result.get("message")
        tool_call = result.get("tool_call")

        response = OrchestratorResult(intent="credit")

        if llm_message:
            response.message = llm_message

        if tool_call:
            response.tool_action = tool_call

        # If no tool and no message, provide fallback
        if not llm_message and not tool_call:
            response.message = "I can help with credit cards, balance, portfolio analysis, and more. What would you like to know?"
            response.tool_action = {"name": "show_credit_menu", "args": {}}

        return response
