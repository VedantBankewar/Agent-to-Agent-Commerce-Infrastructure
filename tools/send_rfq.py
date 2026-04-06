"""
send_rfq — Procurement agent tool.
Create an RFQ, persist it to SQLite, broadcast it to Redis,
and collect live supplier quotes for up to 30 seconds.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from messaging.redis_client import open_quote_window, get_quotes as redis_get_quotes, ping as redis_ping
from utils.logger import get_logger, log_tool_call


DATABASE_PATH    = os.getenv("DATABASE_PATH", "db/hackathon.db")
MARKETPLACE_URL  = os.getenv("MARKETPLACE_URL", "http://localhost:8000")
QUOTE_WAIT_SECS  = 30   # How long to wait for supplier quotes


@dataclass
class RFQResult:
    rfq_id: str
    agent_id: str
    item: str
    quantity: int
    budget: float
    deadline: str
    category: str
    status: str
    created_at: str
    quotes_received: int
    supplier_quotes: list[dict[str, Any]]


def send_rfq(
    agent_id: str,
    item: str,
    quantity: int,
    budget: float,
    deadline: str,
    category: str,
    wait_for_quotes: bool = True,
    timeout_seconds: int | None = None,
) -> RFQResult:
    """
    Create an RFQ and collect supplier quotes.

    Workflow:
      1. Validate agent_id exists in SQLite
      2. Insert RFQ into SQLite via marketplace API
      3. Open Redis quote window (rfq:{id}:quotes, TTL 30s)
      4. Optionally wait up to 30s for supplier quotes to arrive
      5. Return the RFQ record plus collected quotes

    Args:
        agent_id:         Procurement agent creating the RFQ.
        item:            Item / SKU being requested.
        quantity:        Number of units requested.
        budget:          Maximum budget (ALGO, not microALGO).
        deadline:        Delivery deadline as ISO date string.
        category:        Product category for supplier filtering.
        wait_for_quotes: If True, wait up to timeout_seconds for quotes (default True).
        timeout_seconds: Override wait time (default 30s).

    Returns:
        RFQResult with RFQ fields and collected supplier quotes.
    """
    logger = get_logger("send_rfq")
    timeout = timeout_seconds if timeout_seconds is not None else QUOTE_WAIT_SECS

    log_tool_call(
        logger,
        "send_rfq",
        {
            "agent_id": agent_id,
            "item": item,
            "quantity": quantity,
            "budget": budget,
            "deadline": deadline,
            "category": category,
        },
    )

    # -------------------------------------------------------------------------
    # Step 1: Validate agent exists
    # -------------------------------------------------------------------------
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT agent_id FROM agents WHERE agent_id = ?", (agent_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise ValueError(f"Agent {agent_id} not found in database.")

    # -------------------------------------------------------------------------
    # Step 2: Create RFQ via marketplace API (or direct SQLite fallback)
    # -------------------------------------------------------------------------
    rfq_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        import urllib.request

        payload = json.dumps({
            "agent_id": agent_id,
            "item": item,
            "quantity": quantity,
            "budget": budget,
            "deadline": deadline,
            "category": category,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{MARKETPLACE_URL}/rfqs",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 201:
                rfq_data = json.loads(resp.read())
                logger.info("RFQ created via marketplace API", extra={"rfq_id": rfq_id})
    except Exception as exc:
        logger.debug(f"Marketplace API unavailable, writing RFQ directly to SQLite: {exc}")
        # Direct SQLite insert fallback
        cursor.execute(
            """
            INSERT INTO rfqs
                (rfq_id, agent_id, item, quantity, budget, deadline, category, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (rfq_id, agent_id, item, quantity, budget, deadline, category, created_at),
        )
        conn.commit()
        rfq_data = {
            "rfq_id": rfq_id,
            "agent_id": agent_id,
            "item": item,
            "quantity": quantity,
            "budget": budget,
            "deadline": deadline,
            "category": category,
            "status": "open",
            "created_at": created_at,
        }

    conn.close()

    # -------------------------------------------------------------------------
    # Step 3: Open Redis quote window
    # -------------------------------------------------------------------------
    if redis_ping():
        open_quote_window(rfq_id)
        logger.info("Redis quote window opened", extra={"rfq_id": rfq_id, "ttl_s": 30})
    else:
        logger.warning("Redis unavailable, skipping quote window", extra={"rfq_id": rfq_id})

    # -------------------------------------------------------------------------
    # Step 4: Wait for supplier quotes
    # -------------------------------------------------------------------------
    supplier_quotes: list[dict[str, Any]] = []

    if wait_for_quotes and redis_ping():
        elapsed = 0
        interval = 2  # poll every 2 seconds
        while elapsed < timeout:
            time.sleep(interval)
            elapsed += interval
            quotes = redis_get_quotes(rfq_id)
            if quotes:
                supplier_quotes = quotes
                logger.info(
                    "Quotes received",
                    extra={"rfq_id": rfq_id, "count": len(quotes)},
                )
                break

    return RFQResult(
        rfq_id=rfq_data["rfq_id"],
        agent_id=rfq_data["agent_id"],
        item=rfq_data["item"],
        quantity=rfq_data["quantity"],
        budget=rfq_data["budget"],
        deadline=rfq_data["deadline"],
        category=rfq_data["category"],
        status=rfq_data["status"],
        created_at=rfq_data.get("created_at", created_at),
        quotes_received=len(supplier_quotes),
        supplier_quotes=supplier_quotes,
    )
