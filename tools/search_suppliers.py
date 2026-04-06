"""
search_suppliers — Procurement agent tool.
Query the marketplace API for suppliers matching criteria and return a ranked list.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger


DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")


@dataclass
class SupplierMatch:
    supplier_id: str
    name: str
    category: str
    wallet_addr: str
    rating: float
    base_cost: float
    margin_pct: float
    lead_days: int
    warranty_yrs: float
    min_price: float


def search_suppliers(
    category: str | None = None,
    min_rating: float | None = None,
    item: str | None = None,
) -> list[SupplierMatch]:
    """
    Search for suppliers matching the given criteria.

    Calls the marketplace API (GET /suppliers) when available,
    falling back to direct SQLite query if the API is unreachable.

    Args:
        category:   Filter by product category (e.g. "furniture", "office_supplies").
        min_rating: Minimum supplier rating (0–5).
        item:       Optional item/SKU to filter by (JOINs inventory table).

    Returns:
        List of SupplierMatch objects ranked by rating descending.
    """
    logger = get_logger("search_suppliers")

    # Try marketplace API first
    api_base = os.getenv("MARKETPLACE_URL", "http://localhost:8000")
    try:
        import urllib.request

        params: list[str] = []
        if category:
            params.append(f"category={category}")
        if min_rating is not None:
            params.append(f"min_rating={min_rating}")

        query = f"{api_base}/suppliers"
        if params:
            query += "?" + "&".join(params)

        with urllib.request.urlopen(query, timeout=5) as resp:
            if resp.status == 200:
                suppliers = __parse_api_response(resp.read())
                logger.info(
                    "Supplier search via API",
                    extra={"category": category, "count": len(suppliers)},
                )
                return suppliers
    except Exception as exc:
        logger.debug(f"Marketplace API unavailable, falling back to SQLite: {exc}")

    # SQLite fallback
    return _search_sqlite(category, min_rating, item, logger)


def _search_sqlite(
    category: str | None,
    min_rating: float | None,
    item: str | None,
    logger,
) -> list[SupplierMatch]:
    """Direct SQLite query when marketplace API is unreachable."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT DISTINCT
            s.supplier_id,
            s.name,
            s.category,
            s.wallet_addr,
            s.rating,
            s.base_cost,
            s.margin_pct,
            s.lead_days,
            s.warranty_yrs,
            s.min_price
        FROM suppliers s
        LEFT JOIN inventory i ON i.supplier_id = s.supplier_id
        WHERE 1=1
    """
    params: list[Any] = []

    if category:
        query += " AND s.category = ?"
        params.append(category)
    if min_rating is not None:
        query += " AND s.rating >= ?"
        params.append(min_rating)
    if item:
        query += " AND (i.item = ? OR i.item IS NULL)"
        params.append(item)

    query += " ORDER BY s.rating DESC, s.name ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    suppliers = [
        SupplierMatch(
            supplier_id=row["supplier_id"],
            name=row["name"],
            category=row["category"],
            wallet_addr=row["wallet_addr"],
            rating=row["rating"],
            base_cost=row["base_cost"],
            margin_pct=row["margin_pct"],
            lead_days=row["lead_days"],
            warranty_yrs=row["warranty_yrs"],
            min_price=row["min_price"],
        )
        for row in rows
    ]

    logger.info(
        "Supplier search via SQLite",
        extra={"category": category, "count": len(suppliers)},
    )
    return suppliers


def __parse_api_response(raw: bytes) -> list[SupplierMatch]:
    """Parse JSON list from marketplace API into SupplierMatch objects."""
    import json

    data = json.loads(raw)
    return [
        SupplierMatch(
            supplier_id=s["supplier_id"],
            name=s["name"],
            category=s["category"],
            wallet_addr=s["wallet_addr"],
            rating=s["rating"],
            base_cost=s["base_cost"],
            margin_pct=s["margin_pct"],
            lead_days=s["lead_days"],
            warranty_yrs=s["warranty_yrs"],
            min_price=s["min_price"],
        )
        for s in data
    ]
