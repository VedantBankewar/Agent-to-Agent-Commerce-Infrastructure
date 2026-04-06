"""
Procurement Agent — LangChain ReAct agent for buyer-side autonomous procurement.

Accepts a natural-language procurement goal, executes the full pipeline:
supplier search → RFQ broadcast → quote collection → scoring → escrow lock.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from tools.search_suppliers import search_suppliers, SupplierMatch
from tools.send_rfq import send_rfq, RFQResult
from tools.compare_quotes import compare_quotes, CompareResult, ScoredQuote
from tools.sign_escrow import sign_escrow, SignResult
from utils.logger import get_logger, log_agent_thought
from utils.wallet import load_wallet, fund_wallet_from_faucet


AGENTS_DIR = Path(__file__).parent
PROMPTS_DIR = AGENTS_DIR / "prompts"
DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tool wrappers (LangChain-compatible — return plain dicts)
# ---------------------------------------------------------------------------


def _search_suppliers(
    category: str | None = None,
    min_rating: float | None = None,
    item: str | None = None,
) -> dict:
    """Wrapper around search_suppliers."""
    results: list[SupplierMatch] = search_suppliers(category, min_rating, item)
    return {
        "count": len(results),
        "suppliers": [
            {
                "supplier_id": s.supplier_id,
                "name": s.name,
                "category": s.category,
                "wallet_addr": s.wallet_addr,
                "rating": s.rating,
                "base_cost": s.base_cost,
                "margin_pct": s.margin_pct,
                "lead_days": s.lead_days,
                "warranty_yrs": s.warranty_yrs,
                "min_price": s.min_price,
            }
            for s in results
        ],
    }


def _send_rfq(
    agent_id: str,
    item: str,
    quantity: int,
    budget: float,
    deadline: str,
    category: str,
    wait_for_quotes: bool = True,
    timeout_seconds: int | None = None,
) -> dict:
    """Wrapper around send_rfq."""
    result: RFQResult = send_rfq(
        agent_id=agent_id,
        item=item,
        quantity=quantity,
        budget=budget,
        deadline=deadline,
        category=category,
        wait_for_quotes=wait_for_quotes,
        timeout_seconds=timeout_seconds,
    )
    return {
        "rfq_id": result.rfq_id,
        "agent_id": result.agent_id,
        "item": result.item,
        "quantity": result.quantity,
        "budget": result.budget,
        "deadline": result.deadline,
        "category": result.category,
        "status": result.status,
        "created_at": result.created_at,
        "quotes_received": result.quotes_received,
        "supplier_quotes": result.supplier_quotes,
    }


def _compare_quotes(rfq_id: str) -> dict:
    """Wrapper around compare_quotes."""
    result: CompareResult = compare_quotes(rfq_id)
    return {
        "rfq_id": result.rfq_id,
        "quotes_scored": [
            {
                "supplier_id": q.supplier_id,
                "supplier_name": q.supplier_name,
                "unit_price": q.unit_price,
                "total_price": q.total_price,
                "delivery_days": q.delivery_days,
                "warranty_yrs": q.warranty_yrs,
                "supplier_rating": q.supplier_rating,
                "price_score": q.price_score,
                "delivery_score": q.delivery_score,
                "rating_score": q.rating_score,
                "warranty_score": q.warranty_score,
                "total_score": q.total_score,
                "valid_until": q.valid_until,
            }
            for q in result.quotes_scored
        ],
        "winner": {
            "supplier_id": result.winner.supplier_id,
            "supplier_name": result.winner.supplier_name,
            "unit_price": result.winner.unit_price,
            "total_price": result.winner.total_price,
            "delivery_days": result.winner.delivery_days,
            "warranty_yrs": result.winner.warranty_yrs,
            "total_score": result.winner.total_score,
        }
        if result.winner else None,
        "runner_up": {
            "supplier_id": result.runner_up.supplier_id,
            "supplier_name": result.runner_up.supplier_name,
            "total_score": result.runner_up.total_score,
        }
        if result.runner_up else None,
    }


def _sign_escrow(
    rfq_id: str,
    supplier_id: str,
    item: str,
    quantity: int,
    unit_price: float,
    delivery_days: int,
    warranty_yrs: float,
    buyer_agent_id: str,
    budget: float,
    deadline_ts: int,
) -> dict:
    """Wrapper around sign_escrow."""
    result: SignResult = sign_escrow(
        rfq_id=rfq_id,
        supplier_id=supplier_id,
        item=item,
        quantity=quantity,
        unit_price=unit_price,
        delivery_days=delivery_days,
        warranty_yrs=warranty_yrs,
        buyer_agent_id=buyer_agent_id,
        budget=budget,
        deadline_ts=deadline_ts,
    )
    return {
        "deal_id": result.deal_id,
        "rfq_id": result.rfq_id,
        "supplier_id": result.supplier_id,
        "item": result.item,
        "quantity": result.quantity,
        "unit_price": result.unit_price,
        "total_price": result.total_price,
        "delivery_days": result.delivery_days,
        "warranty_yrs": result.warranty_yrs,
        "deal_hash": result.deal_hash,
        "escrow_address": result.escrow_address,
        "app_id": result.app_id,
        "txid": result.txid,
        "confirmed_round": result.confirmed_round,
        "status": result.status,
    }


# ---------------------------------------------------------------------------
# Tool definitions for LangChain
# ---------------------------------------------------------------------------

from langchain_core.tools import BaseTool, Tool


def _build_tools() -> list[BaseTool]:
    return [
        Tool.from_function(
            func=_search_suppliers,
            name="search_suppliers",
            description=(
                "Search the supplier marketplace for vendors matching criteria. "
                "Returns: count, suppliers list with id, name, rating, min_price, etc."
            ),
        ),
        Tool.from_function(
            func=_send_rfq,
            name="send_rfq",
            description=(
                "Broadcast an RFQ to the supplier network. "
                "Returns: rfq_id, status, quotes_received, supplier_quotes."
            ),
        ),
        Tool.from_function(
            func=_compare_quotes,
            name="compare_quotes",
            description=(
                "Score and rank all quotes for an RFQ using weighted multi-criteria. "
                "Returns: quotes_scored, winner, runner_up."
            ),
        ),
        Tool.from_function(
            func=_sign_escrow,
            name="sign_escrow",
            description=(
                "Lock buyer funds in the Algorand escrow contract. "
                "Returns: deal_id, deal_hash, txid, confirmed_round, status."
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


def create_procurement_agent(buyer_agent_id: str) -> Any:
    """
    Create a LangChain agent for the procurement side.

    Args:
        buyer_agent_id: The buyer agent's ID — used to load the wallet.

    Returns:
        A LangGraph CompiledStateGraph agent executor ready to run.
    """
    system_prompt = _load_prompt("procurement.txt")
    system_prompt = system_prompt + f"\n\n[BUYER AGENT ID: {buyer_agent_id}]"

    tools = _build_tools()
    checkpointer = MemorySaver()

    agent = create_agent(
        model=_get_llm(),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )

    return agent


def run_agent_conversation(
    agent: Any,
    user_message: str,
    thread_id: str = "default",
) -> dict:
    """
    Run the agent with a single user message and return the final state.

    Args:
        agent: The LangGraph agent from create_procurement_agent().
        user_message: The natural-language input to the agent.
        thread_id: Checkpointer thread ID for memory persistence.

    Returns:
        The agent's final state dict (contains 'messages').
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    state = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config=config,
    )
    return state


# ---------------------------------------------------------------------------
# Natural-language goal parser
# ---------------------------------------------------------------------------


def parse_procurement_goal(goal: str) -> dict[str, Any]:
    """
    Parse a natural-language procurement goal into structured RFQ fields.

    Examples:
      "Buy 50 ergonomic chairs, budget 300000, by June 15"
      → {"item": "ergonomic chair", "quantity": 50, "budget": 300000, "deadline": "2026-06-15"}

    Args:
        goal: Natural-language procurement request.

    Returns:
        dict with item, quantity, budget, deadline, category.
    """
    goal_lower = goal.lower().strip()

    # Extract quantity — first try specific patterns, then a general number-before-word fallback
    quantity_match = re.search(r"(\d+)\s*(?:x\s*)?(?:ergonomic\s+)?chairs?", goal_lower)
    if not quantity_match:
        quantity_match = re.search(r"(\d+)\s*(?:units?|pieces?|items?|lots?)", goal_lower)
    if not quantity_match:
        # General fallback: any number followed by a word (catches "100 pens", "50 desks", etc.)
        quantity_match = re.search(r"(\d+)\s+\w+", goal_lower)
    quantity = int(quantity_match.group(1)) if quantity_match else 10

    # Extract budget
    budget_match = re.search(
        r"(?:budget|max|up to|under|around)\s*(?:of\s*)?([\d,]+(?:\.\d+)?)",
        goal_lower,
    )
    if not budget_match:
        budget_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:algo|algorand)", goal_lower)
    budget = float(budget_match.group(1).replace(",", "")) if budget_match else 100000.0

    # Extract deadline
    month_map = {
        "january": "01", "jan": "01",
        "february": "02", "feb": "02",
        "march": "03", "mar": "03",
        "april": "04", "apr": "04",
        "may": "05",
        "june": "06", "jun": "06",
        "july": "07", "jul": "07",
        "august": "08", "aug": "08",
        "september": "09", "sep": "09",
        "october": "10", "oct": "10",
        "november": "11", "nov": "11",
        "december": "12", "dec": "12",
    }
    deadline_match = re.search(
        r"(?:by|before|deadline|until)\s+(?:(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?|\d{4}-\d{2}-\d{2})",
        goal_lower,
    )
    if deadline_match:
        # Two regex alternatives are mutually exclusive — group(1) is None iff the ISO date alternative matched
        if deadline_match.group(1) is None:
            deadline = deadline_match.group(0)[-10:]  # ISO date: last 10 chars of "2026-08-01"
        else:
            month_str = deadline_match.group(1).lower()
            day = deadline_match.group(2)
            year = deadline_match.group(3) or str(datetime.now().year)
            month = month_map.get(month_str, "01")
            deadline = f"{year}-{month}-{day.zfill(2)}"
    else:
        deadline = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Infer category
    if any(w in goal_lower for w in ["chair", "desk", "table", "shelf", "cabinet", "furniture"]):
        category = "furniture"
    elif any(w in goal_lower for w in ["pen", "paper", "stapler", "notebook", "supply"]):
        category = "office_supplies"
    else:
        category = "general"

    # Extract item name — find the core product noun after "buy", before "budget"/"by"/","
    # This is independent of the quantity extraction so neither interferes with the other
    item_match = re.search(
        r"^buy\s+([a-z][\w\s]*?)\s*(?:,\s*(?:budget|by|before|until|deadline)|$)",
        goal_lower,
    )
    if item_match:
        item = item_match.group(1).strip()
    else:
        item = goal_lower
        item = re.sub(r"^buy\s+", "", item)
        item = re.sub(r"\s*(?:budget|by|before|until|deadline).*", "", item)
        item = re.sub(r",.*", "", item)
        item = item.strip()
    item = re.sub(r"\d+", "", item)                       # remove stray digits
    item = re.sub(r"[^\w\s]", " ", item)                 # remove punctuation
    item = re.sub(r"\s+", " ", item).strip()             # collapse whitespace

    # Normalise furniture keywords to "chair"; preserve other product nouns as-is
    if re.search(r"(?:ergonomic\s+)?chairs?", item, re.IGNORECASE):
        item = "chair"
    elif not item:
        item = "chair"

    return {
        "item": item,
        "quantity": quantity,
        "budget": budget,
        "deadline": deadline,
        "category": category,
    }


# ---------------------------------------------------------------------------
# High-level run function (CLI / direct use)
# ---------------------------------------------------------------------------


def run_procurement_goal(
    buyer_agent_id: str,
    goal: str,
    max_retries: int = 1,
) -> dict[str, Any]:
    """
    Execute a full procurement workflow from a natural-language goal.

    Pipeline:
      1. Parse goal → structured RFQ fields
      2. Search suppliers
      3. Send RFQ (wait for quotes)
      4. Compare and score quotes
      5. Select winner
      6. Fund wallet if needed
      7. Lock escrow

    Args:
        buyer_agent_id: The procurement agent's ID.
        goal: Natural-language procurement request.
        max_retries: How many times to retry on escrow lock failure.

    Returns:
        dict with the final deal record and key milestones.
    """
    logger = get_logger("procurement_agent")
    logger.info("Starting procurement goal", extra={"goal": goal})

    # Step 1: Parse goal
    parsed = parse_procurement_goal(goal)
    logger.info("Goal parsed", extra=parsed)

    item = parsed["item"]
    quantity = parsed["quantity"]
    budget = parsed["budget"]
    deadline = parsed["deadline"]
    category = parsed["category"]

    deadline_dt = datetime.strptime(deadline, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    deadline_ts = int(deadline_dt.timestamp())

    # Step 2: Search suppliers
    suppliers_result = _search_suppliers(category=category)
    logger.info(
        "Suppliers found",
        extra={"category": category, "count": suppliers_result["count"]},
    )

    if suppliers_result["count"] == 0:
        suppliers_result = _search_suppliers(item=item)
        logger.info("No category matches — searching by item", extra={"item": item})

    # Step 3: Send RFQ
    rfq_result = _send_rfq(
        agent_id=buyer_agent_id,
        item=item,
        quantity=quantity,
        budget=budget,
        deadline=deadline,
        category=category,
        wait_for_quotes=True,
        timeout_seconds=30,
    )
    rfq_id = rfq_result["rfq_id"]
    logger.info(
        "RFQ sent",
        extra={"rfq_id": rfq_id, "quotes_received": rfq_result["quotes_received"]},
    )

    # Step 4: Compare quotes
    compare_result = _compare_quotes(rfq_id)
    winner = compare_result.get("winner")

    if winner is None:
        logger.warning("No quotes received for RFQ", extra={"rfq_id": rfq_id})
        return {
            "status": "no_quotes",
            "rfq_id": rfq_id,
            "goal": goal,
            "parsed": parsed,
        }

    winner_name = winner["supplier_name"]
    winner_id = winner["supplier_id"]
    unit_price = winner["unit_price"]
    total_price = winner["total_price"]
    delivery_days = winner["delivery_days"]
    warranty_yrs = winner["warranty_yrs"]
    total_score = winner["total_score"]

    logger.info(
        "Winner selected",
        extra={
            "rfq_id": rfq_id,
            "winner": winner_name,
            "score": total_score,
            "unit_price": unit_price,
            "total_price": total_price,
        },
    )

    # Step 5: Escrow lock (with optional retry on insufficient funds)
    for attempt in range(max_retries + 1):
        try:
            escrow_result = _sign_escrow(
                rfq_id=rfq_id,
                supplier_id=winner_id,
                item=item,
                quantity=quantity,
                unit_price=unit_price,
                delivery_days=delivery_days,
                warranty_yrs=warranty_yrs,
                buyer_agent_id=buyer_agent_id,
                budget=budget,
                deadline_ts=deadline_ts,
            )
            logger.info(
                "Escrow locked",
                extra={
                    "deal_id": escrow_result["deal_id"],
                    "txid": escrow_result["txid"],
                    "confirmed_round": escrow_result["confirmed_round"],
                },
            )
            return {
                "status": "success",
                "rfq_id": rfq_id,
                "deal_id": escrow_result["deal_id"],
                "supplier_id": winner_id,
                "supplier_name": winner_name,
                "item": item,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "delivery_days": delivery_days,
                "warranty_yrs": warranty_yrs,
                "deal_hash": escrow_result["deal_hash"],
                "escrow_address": escrow_result["escrow_address"],
                "app_id": escrow_result["app_id"],
                "txid": escrow_result["txid"],
                "confirmed_round": escrow_result["confirmed_round"],
                "goal": goal,
                "parsed": parsed,
            }

        except Exception as exc:
            error_lower = str(exc).lower()
            if "overspend" in error_lower or "insufficient" in error_lower:
                logger.warning(
                    "Escrow lock failed — attempting faucet fund",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                try:
                    buyer_wallet = load_wallet(buyer_agent_id)
                    fund_wallet_from_faucet(buyer_wallet.address)
                    logger.info("Wallet funded from faucet", extra={"address": buyer_wallet.address})
                    continue
                except Exception as faucet_error:
                    logger.error("Faucet fund failed", extra={"error": str(faucet_error)})
                    raise
            else:
                logger.error("Escrow lock failed", extra={"error": str(exc)})
                raise

    return {
        "status": "failed",
        "rfq_id": rfq_id,
        "goal": goal,
        "error": "Escrow lock failed after retries",
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the procurement agent with a natural-language goal",
    )
    parser.add_argument(
        "--agent-id",
        required=True,
        help="Procurement agent ID (buyer identity)",
    )
    parser.add_argument(
        "--goal",
        required=True,
        help='Natural-language procurement goal, e.g. "Buy 50 ergonomic chairs, budget 300000, by June 15"',
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Number of retries on escrow lock failure (default 1)",
    )

    args = parser.parse_args()

    result = run_procurement_goal(
        buyer_agent_id=args.agent_id,
        goal=args.goal,
        max_retries=args.max_retries,
    )

    print("\n" + "=" * 60)
    print("PROCUREMENT RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
