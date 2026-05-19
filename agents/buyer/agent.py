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


def _get_llm():
    """Get the LLM instance for the buyer agent.

    Tries Anthropic first, then OpenAI.

    Returns:
        A LangChain chat model instance.

    Raises:
        ValueError: If no API key is configured.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514"),
            temperature=0.3,
            max_tokens=4096,
        )
    elif os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("AGENT_MODEL", "gpt-4o"),
            temperature=0.3,
            max_tokens=4096,
        )
    else:
        raise ValueError(
            "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
        )


def create_buyer_agent(
    context: ProcurementContext,
    session_manager: NegotiationSessionManager,
):
    """Create the autonomous buyer LangGraph ReAct agent.

    Args:
        context: The ProcurementContext with buyer request and state.
        session_manager: The NegotiationSessionManager to use.

    Returns:
        A compiled LangGraph agent ready to invoke.
    """
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver

    llm = _get_llm()
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

    # 5. Create and invoke agent
    agent = create_buyer_agent(context, sm)

    config = {
        "configurable": {"thread_id": f"procurement-{buyer_agent_id}"},
        "recursion_limit": max_iterations,
    }

    try:
        initial_message = (
            f"Begin procurement for {request.quantity} x {request.item}. "
            f"Category: {request.category}. "
            f"Budget: ${request.budget_usd:,.2f} USD. "
            f"Deadline: {request.deadline}. "
            f"Priority: {request.priority.value}. "
            f"Start by discovering suppliers."
        )

        result = agent.invoke(
            {"messages": [("human", initial_message)]},
            config=config,
        )

        # Extract final message
        if result.get("messages"):
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            logger.info("Agent completed", extra={"final_message": content[:200]})

    except Exception as e:
        logger.error("Agent failed", extra={"error": str(e)})
        context.deal_phase = DealPhase.FAILED
        EventBus.emit("agent_error", {
            "error_type": type(e).__name__,
            "message": str(e),
            "details": {},
        })

    return context
