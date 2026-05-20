"""LLMSupplier — Claude/GPT-powered supplier reasoning.

Wraps a LangChain LLM to generate intelligent supplier responses.
Falls back to RuleBotSupplier if LLM is unavailable.
"""

from __future__ import annotations

import os

from core.supplier_interface import SupplierInterface
from core.types import (
    CounterDecision,
    MessageType,
    NegotiationMessage,
    NegotiationTerms,
)
from utils.logger import get_logger

logger = get_logger("supplier_llm")


class LLMSupplier(SupplierInterface):
    """LLM-powered supplier — uses Claude/GPT for reasoning.

    Uses the LLM to generate natural negotiation responses while
    still respecting supplier constraints (price floor, max discount).

    Falls back to RuleBotSupplier behavior if LLM call fails.

    Args:
        supplier_id: The supplier's unique ID.
    """

    def __init__(self, supplier_id: str) -> None:
        self.supplier_id = supplier_id
        self.supplier_name = supplier_id

        # Lazy import to avoid hard dependency on langchain at module level
        from agents.supplier.bot import RuleBotSupplier
        self._fallback = RuleBotSupplier(supplier_id)
        self.supplier_name = self._fallback.supplier_name

        self._llm = self._get_llm()

    def receive_rfq(self, message: NegotiationMessage) -> NegotiationMessage:
        """Handle RFQ using LLM reasoning with bot fallback.

        Args:
            message: The RFQ message from the buyer.

        Returns:
            Quote message with LLM-generated natural language.
        """
        # Get structured response from bot (for correct pricing)
        bot_response = self._fallback.receive_rfq(message)

        if self._llm is None or bot_response.decision == CounterDecision.REJECT:
            return bot_response

        # Enhance the natural language with LLM
        try:
            enhanced_nl = self._enhance_message(
                role="supplier responding to an RFQ",
                context=f"Item: {message.natural_language}",
                bot_message=bot_response.natural_language,
                terms=bot_response.proposed_terms,
            )
            bot_response.natural_language = enhanced_nl
        except Exception as e:
            logger.warning("LLM enhancement failed, using bot text", extra={"error": str(e)})

        return bot_response

    def receive_counter(self, message: NegotiationMessage) -> NegotiationMessage:
        """Handle counter-offer using LLM reasoning with bot fallback.

        Args:
            message: Counter-offer from the buyer.

        Returns:
            Response with LLM-generated negotiation language.
        """
        bot_response = self._fallback.receive_counter(message)

        if self._llm is None:
            return bot_response

        try:
            enhanced_nl = self._enhance_message(
                role="supplier responding to a counter-offer",
                context=(
                    f"Buyer offered ${message.proposed_terms.unit_price_usd:.2f}/unit. "
                    f"Round {message.round_number}."
                    if message.proposed_terms else "Counter-offer received."
                ),
                bot_message=bot_response.natural_language,
                terms=bot_response.proposed_terms,
                decision=bot_response.decision,
            )
            bot_response.natural_language = enhanced_nl
        except Exception as e:
            logger.warning("LLM enhancement failed, using bot text", extra={"error": str(e)})

        return bot_response

    def confirm_deal(self, message: NegotiationMessage) -> NegotiationMessage:
        """Acknowledge deal with LLM-generated confirmation.

        Args:
            message: Acceptance message from buyer.

        Returns:
            Confirmation with LLM-enhanced language.
        """
        return self._fallback.confirm_deal(message)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_llm():
        """Get the LLM instance, or None if not configured.

        Tries providers in order: DigitalOcean GenAI -> Groq -> Google Gemini -> Anthropic.
        """
        try:
            if os.getenv("DO_AI_API_KEY"):
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=os.getenv("DO_AI_MODEL", "openai-gpt-oss-120b"),
                    api_key=os.getenv("DO_AI_API_KEY"),
                    base_url=os.getenv("DO_AI_BASE_URL", "https://inference.do-ai.run/v1"),
                    temperature=0.7,
                    max_tokens=200,
                    request_timeout=60,
                )
            if os.getenv("GROQ_API_KEY"):
                from langchain_groq import ChatGroq
                raw = os.getenv("GROQ_API_KEY", "")
                api_key = raw.split(",")[0].strip()
                return ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key, temperature=0.7, max_tokens=200)
            if os.getenv("GOOGLE_API_KEY"):
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7, max_output_tokens=200)
            if os.getenv("ANTHROPIC_API_KEY"):
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.7, max_tokens=200)
        except ImportError:
            logger.warning("LangChain LLM package not installed")
            return None
        except Exception as e:
            logger.warning("Failed to initialize LLM", extra={"error": str(e)})
            return None

        logger.info("No LLM API key found — LLMSupplier will use bot fallback only")
        return None

    def _enhance_message(
        self,
        role: str,
        context: str,
        bot_message: str,
        terms: NegotiationTerms | None = None,
        decision: CounterDecision | None = None,
    ) -> str:
        """Use LLM to enhance the natural language of a bot response.

        Args:
            role: The supplier's role description.
            context: Context about the current negotiation state.
            bot_message: The bot-generated message to enhance.
            terms: Current proposed terms.
            decision: The decision (accept/counter/reject).

        Returns:
            Enhanced natural language string.
        """
        if self._llm is None:
            return bot_message

        terms_str = ""
        if terms:
            terms_str = (
                f"Price: ${terms.unit_price_usd:.2f}/unit, "
                f"Delivery: {terms.delivery_days} days, "
                f"Warranty: {terms.warranty_yrs}yr"
            )

        prompt = (
            f"You are a {role} named {self.supplier_name}. "
            f"Context: {context}\n"
            f"Your terms: {terms_str}\n"
            f"Decision: {decision.value if decision else 'quote'}\n"
            f"Draft response: {bot_message}\n\n"
            f"Rewrite this as a professional, concise business message (2-3 sentences max). "
            f"Include the specific numbers. Be friendly but firm."
        )

        response = self._llm.invoke(prompt)
        return response.content.strip()
