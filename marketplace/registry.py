"""
FastAPI marketplace for AgentTrade supplier registry and RFQ management.
Provides REST endpoints for supplier discovery, RFQ broadcast, and quote collection.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="AgentTrade Marketplace", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SupplierCreate(BaseModel):
    name: str
    category: str
    wallet_addr: str
    rating: float = Field(default=0.0, ge=0.0, le=5.0)
    min_price: float = Field(gt=0)
    base_cost: float = Field(gt=0)
    margin_pct: float = Field(ge=0)
    lead_days: int = Field(default=7, ge=0)
    warranty_yrs: float = Field(default=1.0, ge=0)
    metadata: dict[str, Any] | None = None


class SupplierUpdate(BaseModel):
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    min_price: float | None = Field(default=None, gt=0)
    lead_days: int | None = Field(default=None, ge=0)
    warranty_yrs: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None


class SupplierResponse(BaseModel):
    supplier_id: str
    name: str
    category: str
    wallet_addr: str
    rating: float
    min_price: float
    base_cost: float
    margin_pct: float
    lead_days: int
    warranty_yrs: float
    created_at: str
    metadata: dict[str, Any] | None = None


class QuoteResponse(BaseModel):
    quote_id: str
    rfq_id: str
    supplier_id: str
    unit_price: float
    total_price: float
    delivery_days: int
    warranty_yrs: float
    valid_until: str
    status: str
    created_at: str
    metadata: dict[str, Any] | None = None


class RFQCreate(BaseModel):
    agent_id: str
    item: str
    quantity: int = Field(gt=0)
    budget: float = Field(ge=0)
    deadline: str  # ISO 8601 date string
    category: str


class RFQResponse(BaseModel):
    rfq_id: str
    agent_id: str
    item: str
    quantity: int
    budget: float
    deadline: str
    category: str
    status: str
    created_at: str
    closed_at: str | None = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Supplier endpoints
# ---------------------------------------------------------------------------

@app.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers(
    category: str | None = None,
    min_rating: float | None = Query(default=None, ge=0.0, le=5.0),
) -> list[dict[str, Any]]:
    """
    List all suppliers, optionally filtered by category and/or minimum rating.
    """
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM suppliers WHERE 1=1"
    params: list[Any] = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if min_rating is not None:
        query += " AND rating >= ?"
        params.append(min_rating)

    query += " ORDER BY rating DESC, name ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict_from_row(row) for row in rows]


@app.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: str) -> dict[str, Any]:
    """Get a single supplier by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return dict_from_row(row)


@app.post("/suppliers", response_model=SupplierResponse, status_code=201)
def create_supplier(data: SupplierCreate) -> dict[str, Any]:
    """
    Register a new supplier. Used by seed_data.py during setup.
    """
    conn = get_db()
    cursor = conn.cursor()

    supplier_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    metadata_json = None
    if data.metadata:
        metadata_json = json.dumps(data.metadata)

    try:
        cursor.execute(
            """
            INSERT INTO suppliers
                (supplier_id, name, category, wallet_addr, rating,
                 min_price, base_cost, margin_pct, lead_days, warranty_yrs,
                 created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                supplier_id,
                data.name,
                data.category,
                data.wallet_addr,
                data.rating,
                data.min_price,
                data.base_cost,
                data.margin_pct,
                data.lead_days,
                data.warranty_yrs,
                created_at,
                metadata_json,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Integrity error: {e}")
    finally:
        conn.close()

    return get_supplier(supplier_id)


@app.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(supplier_id: str, data: SupplierUpdate) -> dict[str, Any]:
    """Update supplier rating or inventory."""
    conn = get_db()
    cursor = conn.cursor()

    # Verify supplier exists
    cursor.execute("SELECT supplier_id FROM suppliers WHERE supplier_id = ?", (supplier_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Supplier not found")

    fields: list[str] = []
    params: list[Any] = []

    if data.rating is not None:
        fields.append("rating = ?")
        params.append(data.rating)
    if data.min_price is not None:
        fields.append("min_price = ?")
        params.append(data.min_price)
    if data.lead_days is not None:
        fields.append("lead_days = ?")
        params.append(data.lead_days)
    if data.warranty_yrs is not None:
        fields.append("warranty_yrs = ?")
        params.append(data.warranty_yrs)
    if data.metadata is not None:
        fields.append("metadata = ?")
        params.append(json.dumps(data.metadata))

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(supplier_id)
    query = f"UPDATE suppliers SET {', '.join(fields)} WHERE supplier_id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()

    return get_supplier(supplier_id)


# ---------------------------------------------------------------------------
# RFQ endpoints
# ---------------------------------------------------------------------------

@app.get("/rfqs", response_model=list[RFQResponse])
def list_rfqs(
    status: str | None = None,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all RFQs, optionally filtered by status or agent."""
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM rfqs WHERE 1=1"
    params: list[Any] = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict_from_row(row) for row in rows]


@app.get("/rfqs/{rfq_id}", response_model=RFQResponse)
def get_rfq(rfq_id: str) -> dict[str, Any]:
    """Get a single RFQ by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rfqs WHERE rfq_id = ?", (rfq_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return dict_from_row(row)


@app.post("/rfqs", response_model=RFQResponse, status_code=201)
def create_rfq(data: RFQCreate) -> dict[str, Any]:
    """
    Create a new RFQ. The procurement agent posts here.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Verify agent exists
    cursor.execute("SELECT agent_id FROM agents WHERE agent_id = ?", (data.agent_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Agent {data.agent_id} not found")

    rfq_id = str(uuid.uuid4())

    try:
        cursor.execute(
            """
            INSERT INTO rfqs (rfq_id, agent_id, item, quantity, budget, deadline, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rfq_id,
                data.agent_id,
                data.item,
                data.quantity,
                data.budget,
                data.deadline,
                data.category,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Integrity error: {e}")
    finally:
        conn.close()

    return get_rfq(rfq_id)


@app.get("/rfqs/{rfq_id}/quotes", response_model=list[QuoteResponse])
def get_rfq_quotes(rfq_id: str) -> list[dict[str, Any]]:
    """
    Fetch all quotes for an RFQ.
    Short-circuits to Redis for live quotes; falls back to SQLite quotes table.
    """
    # Try Redis first for live quotes
    from messaging.redis_client import get_quotes as redis_get_quotes, ping as redis_ping

    if redis_ping():
        live = redis_get_quotes(rfq_id)
        if live:
            return live

    # Fall back to SQLite
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM quotes WHERE rfq_id = ? ORDER BY created_at ASC",
        (rfq_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict_from_row(row) for row in rows]


@app.patch("/rfqs/{rfq_id}/status")
def update_rfq_status(rfq_id: str, status: str) -> dict[str, Any]:
    """Update RFQ status. Valid transitions: open → quotes_received → closed/cancelled."""
    valid = {"quotes_received", "negotiating", "closed", "cancelled"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT rfq_id, status FROM rfqs WHERE rfq_id = ?", (rfq_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="RFQ not found")

    now = datetime.now(timezone.utc).isoformat()
    fields = ["status = ?"]
    params: list[Any] = [status]

    if status in {"closed", "cancelled"}:
        fields.append("closed_at = ?")
        params.append(now)

    params.extend([rfq_id])
    query = f"UPDATE rfqs SET {', '.join(fields)} WHERE rfq_id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()

    return {"rfq_id": rfq_id, "status": status}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
