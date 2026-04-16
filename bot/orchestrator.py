"""Orchestrator — classifies intent, routes to specialist agents, enables cross-agent collaboration."""

import logging
from dataclasses import dataclass, field
from bot.services import llm_service

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    """Result from orchestrator processing."""
    intent: str = "general"
    message: str | None = None           # Text response to send
    products: list[dict] = field(default_factory=list)  # Product cards to show
    credit_tip: str | None = None        # Credit enrichment tip
    show_menu: bool = False              # Show main menu
    tool_action: dict | None = None      # Tool call to execute (name + args)


class Orchestrator:
    def __init__(self):
        from bot.agents.shopping_agent import ShoppingAgent
        from bot.agents.credit_agent import CreditAgent
        self.shopping_agent = ShoppingAgent()
        self.credit_agent = CreditAgent()

    async def process(self, message: str, user_id: int,
                      history: list[dict], session: dict) -> OrchestratorResult:
        """Main entry point — classify, route, enrich."""

        # Step 1: Classify intent
        intent = await llm_service.classify_intent(message, history)
        logger.info(f"Intent: {intent} for '{message[:40]}'")

        # Step 2: Route to agent
        if intent == "menu":
            return OrchestratorResult(intent="menu", show_menu=True)

        elif intent == "shopping":
            result = await self.shopping_agent.handle(message, user_id, history, session)

            # Step 3: Cross-agent credit enrichment
            if result.products:
                tip = await self._get_credit_tip(result.products, user_id)
                result.credit_tip = tip

            return result

        elif intent == "credit":
            return await self.credit_agent.handle(message, user_id, history, session)

        else:  # general
            user_name = session.get("name", "")
            response = await llm_service.general_response(message, history, user_name)
            return OrchestratorResult(
                intent="general",
                message=response or "I'm here to help with shopping and credit! Type /menu to see options.",
            )

    async def _get_credit_tip(self, products: list[dict], user_id: int) -> str | None:
        """Ask Credit Agent for payment optimization tip based on products shown."""
        try:
            from bot.services.database import get_user_cards
            portfolio = await get_user_cards(user_id)
            return await llm_service.credit_enrichment(products, portfolio)
        except Exception as e:
            logger.debug(f"Credit enrichment skipped: {e}")
            # Fallback if DB not available
            from bot.models.cards import DEFAULT_PORTFOLIO
            simple_portfolio = [
                {"card_id": c["id"], "balance": c.get("default_balance", 0),
                 "credit_limit": c.get("default_limit", 0)}
                for c in DEFAULT_PORTFOLIO
            ]
            try:
                return await llm_service.credit_enrichment(products, simple_portfolio)
            except Exception:
                return None


# Singleton
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
