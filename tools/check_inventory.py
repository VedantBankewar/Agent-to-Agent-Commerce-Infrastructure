"""
check_inventory — Supplier agent tool.
Query the SQLite inventory table for item availability and dispatch estimates.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Any


DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")


@dataclass
class InventoryResult:
    available: bool
    dispatch_days: int
    stock_count: int
    reserved_qty: int
    unit_cost: float
    supplier_id: str
    item: str


def check_inventory(
    supplier_id: str,
    item: str,
    quantity: int,
    category: str | None = None,
) -> InventoryResult:
    """
    Check whether a supplier has sufficient stock for the requested item.

    Args:
        supplier_id: The supplier's ID.
        item:        The item name / SKU to check.
        quantity:    The quantity the buyer is requesting.
        category:   Optional category filter.

    Returns:
        InventoryResult with availability status. If the item is not found,
        returns stock_count=0 and available=False.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT i.*, s.lead_days
        FROM inventory i
        JOIN suppliers s ON s.supplier_id = i.supplier_id
        WHERE i.supplier_id = ?
          AND i.item        = ?
    """
    params: list[Any] = [supplier_id, item]

    if category:
        query += " AND i.category = ?"
        params.append(category)

    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return InventoryResult(
            available=False,
            dispatch_days=0,
            stock_count=0,
            reserved_qty=0,
            unit_cost=0.0,
            supplier_id=supplier_id,
            item=item,
        )

    available_qty = row["stock_qty"] - row["reserved_qty"]

    return InventoryResult(
        available=available_qty >= quantity,
        dispatch_days=row["lead_days"],
        stock_count=row["stock_qty"],
        reserved_qty=row["reserved_qty"],
        unit_cost=row["unit_cost"],
        supplier_id=row["supplier_id"],
        item=row["item"],
    )
