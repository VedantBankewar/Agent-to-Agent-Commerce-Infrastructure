"""
calculate_quote — Supplier agent tool.
Compute a quote's unit price, delivery window, warranty, and validity.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")


# How long a quote remains valid after being sent (minutes)
QUOTE_VALIDITY_MINUTES = 30


@dataclass
class QuoteResult:
    unit_price: float
    total_price: float
    delivery_days: int
    warranty_yrs: float
    valid_until: str      # ISO 8601 datetime
    supplier_id: str
    item: str


def calculate_quote(
    supplier_id: str,
    item: str,
    quantity: int,
    category: str | None = None,
) -> QuoteResult | None:
    """
    Compute a supplier's quote for an item.

    Formula:
        unit_price = base_cost × (1 + margin_pct/100) + delivery_charge_per_unit
        total_price = unit_price × quantity

    Args:
        supplier_id: The supplier's ID.
        item:        The item name / SKU.
        quantity:    Number of units.
        category:    Optional category filter.

    Returns:
        QuoteResult, or None if the supplier or item is not found.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT s.supplier_id, s.base_cost, s.margin_pct,
               s.lead_days, s.warranty_yrs,
               i.unit_cost, i.stock_qty, i.reserved_qty
        FROM suppliers s
        LEFT JOIN inventory i ON i.supplier_id = s.supplier_id
                              AND i.item = ?
        WHERE s.supplier_id = ?
    """
    params: list = [item, supplier_id]

    if category:
        query += " AND s.category = ?"
        params.append(category)

    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    base_cost    = row["base_cost"]
    margin_pct   = row["margin_pct"]
    lead_days    = row["lead_days"]
    warranty_yrs = row["warranty_yrs"]
    unit_cost    = row["unit_cost"] or 0.0

    # delivery_charge_per_unit = unit_cost × 2% (handling surcharge)
    delivery_charge = unit_cost * 0.02 if unit_cost > 0 else 0.0

    unit_price  = base_cost * (1 + margin_pct / 100.0) + delivery_charge
    total_price = unit_price * quantity

    valid_until = datetime.now(timezone.utc) + timedelta(minutes=QUOTE_VALIDITY_MINUTES)
    valid_until_iso = valid_until.isoformat()

    return QuoteResult(
        unit_price=round(unit_price, 2),
        total_price=round(total_price, 2),
        delivery_days=lead_days,
        warranty_yrs=warranty_yrs,
        valid_until=valid_until_iso,
        supplier_id=supplier_id,
        item=item,
    )
