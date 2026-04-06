"""
compare_quotes — Procurement agent tool.
Fetch all quotes for an RFQ and score them using the weighted multi-criteria formula.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Any

from messaging.redis_client import get_quotes as redis_get_quotes, ping as redis_ping
from utils.logger import get_logger, log_tool_call


DATABASE_PATH   = os.getenv("DATABASE_PATH", "db/hackathon.db")


# Scoring weights — must match CLAUDE.md exactly
WEIGHT_PRICE     = 0.40
WEIGHT_DELIVERY  = 0.30
WEIGHT_RATING    = 0.20
WEIGHT_WARRANTY  = 0.10


@dataclass
class ScoredQuote:
    supplier_id: str
    supplier_name: str
    unit_price: float
    total_price: float
    delivery_days: int
    warranty_yrs: float
    supplier_rating: float
    price_score: float
    delivery_score: float
    rating_score: float
    warranty_score: float
    total_score: float
    valid_until: str


@dataclass
class CompareResult:
    rfq_id: str
    quotes_scored: list[ScoredQuote]
    winner: ScoredQuote | None
    runner_up: ScoredQuote | None


def compare_quotes(rfq_id: str) -> CompareResult:
    """
    Score all quotes for an RFQ using the weighted multi-criteria formula.

    Scoring formula (from CLAUDE.md):
        Score = (price_score    × 0.40)
              + (delivery_score × 0.30)
              + (rating_score   × 0.20)
              + (warranty_score × 0.10)

    Normalised sub-scores (each 0–100):
        price_score    = (min_price / supplier_price) × 100
        delivery_score = (min_days  / supplier_days)  × 100
        rating_score   = (supplier_rating / max_rating) × 100
        warranty_score = (supplier_warranty_yrs / max_warranty_yrs) × 100

    Args:
        rfq_id: The RFQ to score quotes for.

    Returns:
        CompareResult with all scored quotes, winner, and runner-up.
    """
    logger = get_logger("compare_quotes")

    log_tool_call(logger, "compare_quotes", {"rfq_id": rfq_id})

    # -------------------------------------------------------------------------
    # Step 1: Collect quotes (Redis first, fall back to SQLite)
    # -------------------------------------------------------------------------
    raw_quotes: list[dict[str, Any]] = []

    if redis_ping():
        live = redis_get_quotes(rfq_id)
        if live:
            raw_quotes = live
            logger.debug("Quotes fetched from Redis", extra={"rfq_id": rfq_id, "count": len(live)})

    if not raw_quotes:
        # SQLite fallback
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT q.*, s.name AS supplier_name, s.rating AS supplier_rating
            FROM quotes q
            JOIN suppliers s ON s.supplier_id = q.supplier_id
            WHERE q.rfq_id = ?
            ORDER BY q.created_at ASC
            """,
            (rfq_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        raw_quotes = [dict(row) for row in rows]
        logger.debug("Quotes fetched from SQLite", extra={"rfq_id": rfq_id, "count": len(raw_quotes)})

    if not raw_quotes:
        logger.info("No quotes found for RFQ", extra={"rfq_id": rfq_id})
        return CompareResult(rfq_id=rfq_id, quotes_scored=[], winner=None, runner_up=None)

    # -------------------------------------------------------------------------
    # Step 2: Enrich with supplier metadata
    # -------------------------------------------------------------------------
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    enriched: list[dict[str, Any]] = []
    for q in raw_quotes:
        cursor.execute(
            "SELECT name, rating, warranty_yrs FROM suppliers WHERE supplier_id = ?",
            (q["supplier_id"],),
        )
        row = cursor.fetchone()
        if row:
            enriched.append({
                **q,
                "supplier_name": row["name"],
                "supplier_rating": row["rating"],
                "warranty_yrs": row["warranty_yrs"],
            })

    conn.close()

    # -------------------------------------------------------------------------
    # Step 3: Compute normalisation baselines (min price, min days, max rating, max warranty)
    # -------------------------------------------------------------------------
    prices  = [q["unit_price"]   for q in enriched if q.get("unit_price")]
    days    = [q["delivery_days"] for q in enriched if q.get("delivery_days")]
    ratings = [q["supplier_rating"] for q in enriched if q.get("supplier_rating")]
    warranties = [q["warranty_yrs"] for q in enriched if q.get("warranty_yrs")]

    min_price    = min(prices)   if prices   else 0.0
    min_days     = min(days)     if days     else 0
    max_rating   = max(ratings)  if ratings  else 5.0
    max_warranty = max(warranties) if warranties else 1.0

    # Guard against zero/min values to avoid division errors
    if min_price    == 0: min_price    = 1.0
    if min_days     == 0: min_days     = 1
    if max_rating   == 0: max_rating   = 1.0
    if max_warranty == 0: max_warranty = 1.0

    # -------------------------------------------------------------------------
    # Step 4: Score each quote
    # -------------------------------------------------------------------------
    scored: list[ScoredQuote] = []

    for q in enriched:
        price_score    = (min_price / q["unit_price"]) * 100
        delivery_score = (min_days  / q["delivery_days"]) * 100
        rating_score   = (q["supplier_rating"] / max_rating) * 100
        warranty_score = (q["warranty_yrs"] / max_warranty) * 100

        total_score = (
            price_score    * WEIGHT_PRICE
          + delivery_score * WEIGHT_DELIVERY
          + rating_score   * WEIGHT_RATING
          + warranty_score * WEIGHT_WARRANTY
        )

        scored.append(ScoredQuote(
            supplier_id     =q["supplier_id"],
            supplier_name   =q["supplier_name"],
            unit_price      =q["unit_price"],
            total_price     =q.get("total_price", q["unit_price"]),
            delivery_days   =q["delivery_days"],
            warranty_yrs    =q["warranty_yrs"],
            supplier_rating=q["supplier_rating"],
            price_score     =round(price_score, 2),
            delivery_score  =round(delivery_score, 2),
            rating_score    =round(rating_score, 2),
            warranty_score  =round(warranty_score, 2),
            total_score     =round(total_score, 2),
            valid_until     =q.get("valid_until", ""),
        ))

    # Sort descending by total_score
    scored.sort(key=lambda x: x.total_score, reverse=True)

    winner    = scored[0] if len(scored) >= 1 else None
    runner_up = scored[1] if len(scored) >= 2 else None

    logger.info(
        "Quotes scored",
        extra={
            "rfq_id":  rfq_id,
            "count":   len(scored),
            "winner":  winner.supplier_name  if winner else None,
            "top_score": winner.total_score if winner else None,
        },
    )

    return CompareResult(
        rfq_id=rfq_id,
        quotes_scored=scored,
        winner=winner,
        runner_up=runner_up,
    )
