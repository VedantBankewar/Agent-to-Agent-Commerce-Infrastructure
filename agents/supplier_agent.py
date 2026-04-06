"""
Supplier Agent — LangChain ReAct agent for seller-side autonomous negotiation.

Receives incoming RFQ events via polling or HTTP webhook, processes them with
the supplier's inventory and pricing tools, and submits quotes to the marketplace.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time as time_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from tools.check_inventory import check_inventory, InventoryResult
from tools.calculate_quote import calculate_quote, QuoteResult
from tools.evaluate_counter import evaluate_counter, EvaluationResult
from tools.submit_proof import submit_proof
from utils.logger import get_logger, log_agent_thought


AGENTS_DIR = Path(__file__).parent
PROMPTS_DIR = AGENTS_DIR / "prompts"
DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")
MARKETPLACE_URL = os.getenv("MARKETPLACE_URL", "http://localhost:8000")


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tool wrappers (LangChain-compatible — return plain dicts)
# ---------------------------------------------------------------------------


def _check_inventory(
    supplier_id: str,
    item: str,
    quantity: int,
    category: str | None = None,
) -> dict:
    """Wrapper around check_inventory."""
    result: InventoryResult = check_inventory(supplier_id, item, quantity, category)
    return {
        "available": result.available,
        "dispatch_days": result.dispatch_days,
        "stock_count": result.stock_count,
        "reserved_qty": result.reserved_qty,
        "unit_cost": result.unit_cost,
        "supplier_id": result.supplier_id,
        "item": result.item,
    }


def _calculate_quote(
    supplier_id: str,
    item: str,
    quantity: int,
    category: str | None = None,
) -> dict:
    """Wrapper around calculate_quote."""
    result: QuoteResult | None = calculate_quote(supplier_id, item, quantity, category)
    if result is None:
        return {"error": f"No quote could be calculated for supplier {supplier_id}, item {item}."}
    return {
        "unit_price": result.unit_price,
        "total_price": result.total_price,
        "delivery_days": result.delivery_days,
        "warranty_yrs": result.warranty_yrs,
        "valid_until": result.valid_until,
        "supplier_id": result.supplier_id,
        "item": result.item,
    }


def _evaluate_counter(
    supplier_id: str,
    rfq_id: str,
    counter_price: float,
    round_number: int = 1,
) -> dict:
    """Wrapper around evaluate_counter."""
    result: EvaluationResult = evaluate_counter(supplier_id, rfq_id, counter_price, round_number)
    return {
        "decision": result.decision,
        "unit_price": result.unit_price,
        "delivery_days": result.delivery_days,
        "warranty_yrs": result.warranty_yrs,
        "message": result.message,
        "round": result.round,
    }


def _submit_proof(deal_id: str, delivery_proof: dict | None = None) -> dict:
    """Wrapper around submit_proof."""
    return submit_proof(deal_id, delivery_proof)


# ---------------------------------------------------------------------------
# Tool definitions for LangChain
# ---------------------------------------------------------------------------

from langchain_core.tools import BaseTool


def _build_tools() -> list[BaseTool]:
    """Build the list of LangChain tools for the supplier agent."""
    from langchain_core.tools import Tool

    return [
        Tool.from_function(
            func=_check_inventory,
            name="check_inventory",
            description=(
                "Query your inventory to verify you can fulfill an order. "
                "Returns: available, dispatch_days, stock_count, reserved_qty, unit_cost."
            ),
        ),
        Tool.from_function(
            func=_calculate_quote,
            name="calculate_quote",
            description=(
                "Compute your quoted price for an item. "
                "Returns: unit_price, total_price, delivery_days, warranty_yrs, valid_until."
            ),
        ),
        Tool.from_function(
            func=_evaluate_counter,
            name="evaluate_counter",
            description=(
                "Evaluate an incoming counter-offer from the procurement agent. "
                "Returns: decision (accept/counter/reject), unit_price, message."
            ),
        ),
        Tool.from_function(
            func=_submit_proof,
            name="submit_proof",
            description=(
                "Anchor your delivery proof on Algorand to trigger escrow release. "
                "Returns: proof_hash, txid, confirmed_round, status."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def _get_llm():
    """Return the configured LLM."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-20250514", anthropic_api_key=api_key, temperature=0.3)

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", openai_api_key=openai_key, temperature=0.3)

    raise EnvironmentError(
        "Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set. "
        "Set one in .env to enable LLM calls."
    )


def create_supplier_agent(supplier_id: str) -> Any:
    """
    Create a LangChain agent for a specific supplier.

    Args:
        supplier_id: The supplier's ID — used to scope inventory and quotes.

    Returns:
        A LangGraph CompiledStateGraph agent executor ready to run.
    """
    system_prompt = _load_prompt("supplier.txt")
    system_prompt = system_prompt + f"\n\n[SUPPLIER ID: {supplier_id}]"

    tools = _build_tools()
    checkpointer = MemorySaver()

    agent = create_agent(
        model=_get_llm(),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )

    return agent


def run_agent_with_messages(agent: Any, messages: list, thread_id: str = "default") -> dict:
    """
    Run the agent with a list of messages and return the final state.

    Args:
        agent: The LangGraph agent from create_supplier_agent().
        messages: List of HumanMessage objects (conversation history).
        thread_id: Checkpointer thread ID for memory persistence.

    Returns:
        The agent's final state dict (contains 'messages').
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    state = agent.invoke({"messages": messages}, config=config)
    return state


# ---------------------------------------------------------------------------
# Quote submission to marketplace
# ---------------------------------------------------------------------------


def submit_quote_to_marketplace(
    rfq_id: str,
    supplier_id: str,
    item: str,
    quantity: int,
    unit_price: float,
    total_price: float,
    delivery_days: int,
    warranty_yrs: float,
    valid_until: str,
) -> bool:
    """POST a supplier's quote to the marketplace API."""
    import urllib.request

    payload = json.dumps({
        "rfq_id": rfq_id,
        "supplier_id": supplier_id,
        "item": item,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": total_price,
        "delivery_days": delivery_days,
        "warranty_yrs": warranty_yrs,
        "valid_until": valid_until,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{MARKETPLACE_URL}/rfqs/{rfq_id}/quotes",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# RFQ polling loop
# ---------------------------------------------------------------------------


def fetch_pending_rfqs(supplier_id: str) -> list[dict[str, Any]]:
    """Poll marketplace API for open RFQs relevant to this supplier."""
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{MARKETPLACE_URL}/rfqs?status=open",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                rfqs: list[dict] = json.loads(resp.read())
                conn = sqlite3.connect(DATABASE_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT category FROM suppliers WHERE supplier_id = ?",
                    (supplier_id,),
                )
                row = cursor.fetchone()
                conn.close()
                if row is None:
                    return []
                my_category = row["category"]
                return [r for r in rfqs if r.get("category") == my_category]
    except Exception:
        pass
    return []


def run_supplier_agent(
    supplier_id: str,
    poll_interval: int = 10,
) -> None:
    """
    Run the supplier agent event loop (polling mode).

    Args:
        supplier_id: The supplier ID this agent represents.
        poll_interval: Seconds between marketplace polls.
    """
    logger = get_logger("supplier_agent")
    logger.info("Starting supplier agent", extra={"supplier_id": supplier_id, "mode": "poll"})

    agent = create_supplier_agent(supplier_id)
    checkpointer = MemorySaver()
    # Re-bind checkpointer to agent if needed (agent from create_agent already has it)

    while True:
        try:
            rfqs = fetch_pending_rfqs(supplier_id)
            for rfq in rfqs:
                rfq_id = rfq["rfq_id"]
                item = rfq["item"]
                quantity = rfq["quantity"]

                log_agent_thought(
                    logger,
                    f"Processing RFQ {rfq_id}: {quantity}x {item}",
                    {"rfq_id": rfq_id, "item": item, "quantity": quantity},
                )

                # Run the agent for this RFQ
                config: RunnableConfig = {"configurable": {"thread_id": f"rfq-{rfq_id}"}}
                messages = [
                    HumanMessage(
                        content=(
                            f"You have received a new RFQ.\n"
                            f"RFQ ID: {rfq_id}\n"
                            f"Item: {item}\n"
                            f"Quantity: {quantity}\n"
                            f"Category: {rfq.get('category', 'general')}\n"
                            f"Please check your inventory, calculate a quote, and submit it."
                        )
                    )
                ]

                try:
                    state = agent.invoke({"messages": messages}, config=config)
                    last_msg = state["messages"][-1] if state.get("messages") else None
                    logger.info(
                        "Agent completed RFQ",
                        extra={
                            "rfq_id": rfq_id,
                            "response": str(last_msg)[:200] if last_msg else None,
                        },
                    )
                except Exception as agent_error:
                    logger.error("Agent error", extra={"rfq_id": rfq_id, "error": str(agent_error)})

        except Exception as exc:
            logger.error("Supplier agent loop error", extra={"error": str(exc)})

        time_module.sleep(poll_interval)


# ---------------------------------------------------------------------------
# FastAPI HTTP server for RFQ events
# ---------------------------------------------------------------------------


def start_rfq_server(supplier_id: str, port: int = 8001) -> None:
    """
    Start a FastAPI HTTP server that receives RFQ events and triggers the agent.

    Args:
        supplier_id: The supplier ID this agent represents.
        port: Port to listen on.
    """
    from fastapi import FastAPI, HTTPException
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger = get_logger("supplier_agent.http")
        logger.info("RFQ HTTP server started", extra={"supplier_id": supplier_id, "port": port})
        yield
        logger.info("RFQ HTTP server shutting down")

    app = FastAPI(title=f"Supplier Agent {supplier_id}", lifespan=lifespan)

    agent = create_supplier_agent(supplier_id)
    checkpointer = MemorySaver()

    @app.post("/rfq")
    async def receive_rfq(payload: dict):
        logger = get_logger("supplier_agent.http")
        rfq_id = payload.get("rfq_id")
        item = payload.get("item")
        quantity = payload.get("quantity")

        if not rfq_id or not item or not quantity:
            raise HTTPException(status_code=400, detail="Missing required fields: rfq_id, item, quantity")

        log_agent_thought(
            logger,
            f"Received RFQ event: {rfq_id} — {quantity}x {item}",
            {"rfq_id": rfq_id, "item": item, "quantity": quantity},
        )

        config: RunnableConfig = {"configurable": {"thread_id": f"rfq-{rfq_id}"}}
        messages = [
            HumanMessage(
                content=(
                    f"You have received a new RFQ.\n"
                    f"RFQ ID: {rfq_id}\n"
                    f"Item: {item}\n"
                    f"Quantity: {quantity}\n"
                    f"Category: {payload.get('category', 'general')}\n"
                    f"Please check your inventory, calculate a quote, and submit it."
                )
            )
        ]

        try:
            state = agent.invoke({"messages": messages}, config=config)
            last_msg = state["messages"][-1] if state.get("messages") else None
            return {"status": "processed", "rfq_id": rfq_id, "response": str(last_msg)[:500] if last_msg else None}
        except Exception as exc:
            logger.error("Agent processing error", extra={"rfq_id": rfq_id, "error": str(exc)})
            raise HTTPException(status_code=500, detail=str(exc))

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a supplier agent")
    parser.add_argument("--supplier-id", required=True, help="Supplier ID this agent represents")
    parser.add_argument(
        "--mode",
        choices=["poll", "http"],
        default="poll",
        help="Event delivery mode: poll (default) or http server",
    )
    parser.add_argument("--port", type=int, default=8001, help="HTTP server port (only for --mode http)")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between marketplace polls (only for --mode poll)",
    )

    args = parser.parse_args()

    if args.mode == "http":
        start_rfq_server(args.supplier_id, args.port)
    else:
        run_supplier_agent(args.supplier_id, poll_interval=args.poll_interval)
