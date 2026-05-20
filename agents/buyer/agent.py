"""Autonomous buyer agent factory and runner for AgentTrade v2.

Creates a LangGraph ReAct agent with 8 tools that autonomously drives
the full procurement lifecycle: discovery -> negotiation -> escrow lock.
"""

from __future__ import annotations

import os
from typing import Any

from core.events import EventBus
from core.negotiation import NegotiationSessionManager
from core.supplier_interface import SupplierRegistry
from core.types import (
    DealPhase,
    ProcurementContext,
    ProcurementRequest,
)
from agents.buyer.prompts import build_buyer_prompt
from agents.buyer.tools import build_buyer_tools
from agents.supplier.bot import RuleBotSupplier
from utils.logger import get_logger

logger = get_logger("buyer_agent")

MAX_ITERATIONS = 30

# Module-level Groq key rotation state (kept as fallback)
_groq_keys: list[str] = []
_groq_key_index: int = 0


def _get_groq_keys() -> list[str]:
    """Parse and cache Groq API keys from environment."""
    global _groq_keys
    if not _groq_keys:
        raw = os.getenv("GROQ_API_KEY", "")
        _groq_keys = [k.strip() for k in raw.split(",") if k.strip()]
    return _groq_keys


def _rotate_groq_key() -> str | None:
    """Rotate to the next Groq API key. Returns the new key or None if exhausted."""
    global _groq_key_index
    keys = _get_groq_keys()
    if len(keys) <= 1:
        return None
    _groq_key_index = (_groq_key_index + 1) % len(keys)
    logger.info(f"Rotated to Groq key {_groq_key_index + 1}/{len(keys)}")
    return keys[_groq_key_index]


def _get_llm(groq_key_override: str | None = None):
    """Get the LLM instance for the buyer agent.

    Tries providers in order: DigitalOcean GenAI -> Groq -> Google Gemini -> Anthropic.

    Args:
        groq_key_override: Optional specific Groq API key to use (fallback only).

    Returns:
        A LangChain chat model instance.

    Raises:
        ValueError: If no API key is configured or all providers fail.
    """
    errors = []

    if os.getenv("DO_AI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            model = os.getenv("DO_AI_MODEL", "openai-gpt-oss-120b")
            logger.info(f"Using DigitalOcean GenAI: {model}")
            return ChatOpenAI(
                model=model,
                api_key=os.getenv("DO_AI_API_KEY"),
                base_url=os.getenv("DO_AI_BASE_URL", "https://inference.do-ai.run/v1"),
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as e:
            errors.append(f"DigitalOcean GenAI: {e}")

    groq_keys = _get_groq_keys()
    if groq_keys:
        try:
            from langchain_groq import ChatGroq
            model = os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile")
            if groq_key_override:
                api_key = groq_key_override
            else:
                api_key = groq_keys[_groq_key_index % len(groq_keys)]
            if len(groq_keys) > 1:
                logger.info(f"Using Groq key {(_groq_key_index % len(groq_keys)) + 1}/{len(groq_keys)}")
            return ChatGroq(model=model, api_key=api_key, temperature=0.3, max_tokens=4096)
        except Exception as e:
            errors.append(f"Groq: {e}")

    if os.getenv("GOOGLE_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=os.getenv("AGENT_MODEL", "gemini-2.0-flash"),
                temperature=0.3,
                max_output_tokens=4096,
            )
        except Exception as e:
            errors.append(f"Google: {e}")

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514"),
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as e:
            errors.append(f"Anthropic: {e}")

    if errors:
        raise ValueError(f"All LLM providers failed: {'; '.join(errors)}")
    else:
        raise ValueError(
            "No LLM API key found. Set DO_AI_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY."
        )


def create_buyer_agent(
    context: ProcurementContext,
    session_manager: NegotiationSessionManager,
    groq_key_override: str | None = None,
):
    """Create the autonomous buyer LangGraph ReAct agent.

    Args:
        context: The ProcurementContext with buyer request and state.
        session_manager: The NegotiationSessionManager to use.
        groq_key_override: Optional specific Groq API key to use.

    Returns:
        A compiled LangGraph agent ready to invoke.
    """
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver

    llm = _get_llm(groq_key_override=groq_key_override)
    tools = build_buyer_tools(session_manager)
    prompt = build_buyer_prompt(context)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt,
        checkpointer=MemorySaver(),
    )

    return agent


def run_buyer_agent(
    buyer_agent_id: str,
    request: ProcurementRequest,
    db_path: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> ProcurementContext:
    """Run the full autonomous procurement agent.

    Creates the context, session manager, registers supplier bots,
    and runs the agent to completion.

    Args:
        buyer_agent_id: The buyer agent's ID (for wallet loading).
        request: The structured ProcurementRequest from the buyer.
        db_path: Optional database path override.
        max_iterations: Maximum tool calls before stopping.

    Returns:
        The final ProcurementContext with deal results.
    """
    logger.info(
        "Starting autonomous buyer agent",
        extra={
            "buyer_id": buyer_agent_id,
            "item": request.item,
            "budget": request.budget_usd,
            "priority": request.priority.value,
        },
    )

    # 1. Create context
    context = ProcurementContext(
        buyer_agent_id=buyer_agent_id,
        request=request,
    )

    # 2. Create session manager
    sm = NegotiationSessionManager(
        context=context,
        db_path=db_path or os.getenv("DATABASE_PATH", "db/hackathon.db"),
    )

    # 3. Register default supplier factory (RuleBotSupplier for all)
    SupplierRegistry.set_default_factory(RuleBotSupplier)

    # 4. Emit agent started
    EventBus.emit("agent_started", {
        "buyer_id": buyer_agent_id,
        "request": {
            "item": request.item,
            "category": request.category,
            "quantity": request.quantity,
            "budget_usd": request.budget_usd,
            "deadline": request.deadline,
            "priority": request.priority.value,
        },
    })

    # 5. Create and invoke agent (with Groq key rotation on rate limits)
    groq_keys = _get_groq_keys()
    max_retries = max(len(groq_keys), 1)

    initial_message = (
        f"Begin procurement for {request.quantity} x {request.item}. "
        f"Category: {request.category}. "
        f"Budget: ${request.budget_usd:,.2f} USD. "
        f"Deadline: {request.deadline}. "
        f"Priority: {request.priority.value}. "
        f"Start by discovering suppliers."
    )

    for attempt in range(max_retries):
        agent = create_buyer_agent(context, sm)

        config = {
            "configurable": {"thread_id": f"procurement-{buyer_agent_id}-{attempt}"},
            "recursion_limit": max_iterations,
        }

        try:
            result = agent.invoke(
                {"messages": [("human", initial_message)]},
                config=config,
            )

            # Extract final message
            if result.get("messages"):
                last_msg = result["messages"][-1]
                content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                logger.info("Agent completed", extra={"final_message": content[:200]})

            break  # Success — exit retry loop

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "rate_limit" in error_str or "429" in error_str or "rate limit" in error_str

            if is_rate_limit and attempt < max_retries - 1:
                new_key = _rotate_groq_key()
                if new_key:
                    logger.warning(
                        f"Rate limited on Groq key {attempt + 1}, rotating to next key",
                        extra={"attempt": attempt + 1},
                    )
                    continue

            logger.error("Agent failed", extra={"error": str(e)})
            context.deal_phase = DealPhase.FAILED
            EventBus.emit("agent_error", {
                "error_type": type(e).__name__,
                "message": str(e),
                "details": {},
            })
            break

    return context
