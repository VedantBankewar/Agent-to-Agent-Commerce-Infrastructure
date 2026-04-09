"""
test_compare_quotes — Unit tests for the quote scoring formula.

Verifies the weighted multi-criteria scorer against known inputs,
using an in-memory SQLite DB so no production data is touched.

Formula:
    Score = (min_price/price × 0.40) + (min_days/days × 0.30)
          + (rating/max_rating × 0.20) + (warranty/max_warranty × 0.10)
"""

from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures — in-memory DB with schema + helpers
# ---------------------------------------------------------------------------

SCHEMA_FILE = ROOT / "db" / "schema.sql"


def _create_test_db() -> str:
    """Create a temp SQLite file with the project schema. Returns path."""
    db_path = str(ROOT / "tests" / f"_test_quotes_{uuid.uuid4().hex[:8]}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_FILE.read_text())
    conn.close()
    return db_path


def _insert_agent(conn: sqlite3.Connection, agent_id: str = "test-buyer") -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO agents (agent_id, agent_type, name, wallet_addr, created_at) "
        "VALUES (?, 'procurement', 'TestBuyer', ?, ?)",
        (agent_id, f"ADDR_{agent_id}", now),
    )


def _insert_supplier(
    conn: sqlite3.Connection,
    supplier_id: str,
    name: str,
    rating: float = 4.0,
    warranty_yrs: float = 1.0,
    category: str = "furniture",
    min_price: float = 50.0,
    base_cost: float = 80.0,
    margin_pct: float = 20.0,
    lead_days: int = 7,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO suppliers "
        "(supplier_id, name, category, wallet_addr, rating, min_price, base_cost, "
        "margin_pct, lead_days, warranty_yrs, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (supplier_id, name, category, f"ADDR_{supplier_id}", rating,
         min_price, base_cost, margin_pct, lead_days, warranty_yrs, now),
    )


def _insert_rfq(
    conn: sqlite3.Connection,
    rfq_id: str,
    agent_id: str = "test-buyer",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO rfqs "
        "(rfq_id, agent_id, item, quantity, budget, deadline, category, status, created_at) "
        "VALUES (?, ?, 'chairs', 50, 10000, '2026-06-15', 'furniture', 'open', ?)",
        (rfq_id, agent_id, now),
    )


def _insert_quote(
    conn: sqlite3.Connection,
    rfq_id: str,
    supplier_id: str,
    unit_price: float,
    total_price: float,
    delivery_days: int,
    warranty_yrs: float = 1.0,
) -> str:
    quote_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    valid_until = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    conn.execute(
        "INSERT INTO quotes "
        "(quote_id, rfq_id, supplier_id, unit_price, total_price, delivery_days, "
        "warranty_yrs, valid_until, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
        (quote_id, rfq_id, supplier_id, unit_price, total_price,
         delivery_days, warranty_yrs, valid_until, now),
    )
    return quote_id


@pytest.fixture
def test_db(tmp_path):
    """Create a fresh test DB and patch DATABASE_PATH for compare_quotes."""
    db_path = str(tmp_path / "test_quotes.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_FILE.read_text())
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_single_quote_gets_perfect_score(test_db):
    """A lone quote should score 100.0 (it is both min and max for everything)."""
    conn = sqlite3.connect(test_db)
    _insert_agent(conn)
    rfq_id = "rfq-single"
    _insert_supplier(conn, "sup-A", "SupplierA", rating=4.5, warranty_yrs=2.0)
    _insert_rfq(conn, rfq_id)
    _insert_quote(conn, rfq_id, "sup-A",
                  unit_price=100.0, total_price=5000.0,
                  delivery_days=7, warranty_yrs=2.0)
    conn.commit()
    conn.close()

    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        # Re-import to pick up patched env
        import importlib
        import tools.compare_quotes as cq
        importlib.reload(cq)

        result = cq.compare_quotes(rfq_id)

    assert len(result.quotes_scored) == 1
    assert result.winner is not None
    assert result.winner.total_score == 100.0
    assert result.runner_up is None


def test_two_quotes_cheaper_wins_on_price(test_db):
    """Between two quotes with identical delivery/rating/warranty, cheaper should win."""
    conn = sqlite3.connect(test_db)
    _insert_agent(conn)
    rfq_id = "rfq-price"
    _insert_supplier(conn, "sup-cheap", "CheapSupplier", rating=4.0, warranty_yrs=1.0)
    _insert_supplier(conn, "sup-expensive", "ExpensiveSupplier", rating=4.0, warranty_yrs=1.0)
    _insert_rfq(conn, rfq_id)
    _insert_quote(conn, rfq_id, "sup-cheap",
                  unit_price=90.0, total_price=4500.0,
                  delivery_days=10, warranty_yrs=1.0)
    _insert_quote(conn, rfq_id, "sup-expensive",
                  unit_price=100.0, total_price=5000.0,
                  delivery_days=10, warranty_yrs=1.0)
    conn.commit()
    conn.close()

    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.compare_quotes as cq
        importlib.reload(cq)

        result = cq.compare_quotes(rfq_id)

    assert result.winner.supplier_id == "sup-cheap"
    assert result.runner_up.supplier_id == "sup-expensive"
    # Verify the price subscores differ correctly
    # Cheap: price_score = (90/90)*100 = 100.0
    # Expensive: price_score = (90/100)*100 = 90.0
    assert result.winner.price_score == 100.0
    assert result.runner_up.price_score == 90.0


def test_two_quotes_faster_delivery_wins(test_db):
    """Same price/rating/warranty — faster delivery should win (30% weight)."""
    conn = sqlite3.connect(test_db)
    _insert_agent(conn)
    rfq_id = "rfq-delivery"
    _insert_supplier(conn, "sup-fast", "FastSupplier", rating=4.0, warranty_yrs=1.0)
    _insert_supplier(conn, "sup-slow", "SlowSupplier", rating=4.0, warranty_yrs=1.0)
    _insert_rfq(conn, rfq_id)
    _insert_quote(conn, rfq_id, "sup-fast",
                  unit_price=100.0, total_price=5000.0,
                  delivery_days=5, warranty_yrs=1.0)
    _insert_quote(conn, rfq_id, "sup-slow",
                  unit_price=100.0, total_price=5000.0,
                  delivery_days=10, warranty_yrs=1.0)
    conn.commit()
    conn.close()

    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.compare_quotes as cq
        importlib.reload(cq)

        result = cq.compare_quotes(rfq_id)

    assert result.winner.supplier_id == "sup-fast"
    # Fast: delivery_score = (5/5)*100 = 100.0
    # Slow: delivery_score = (5/10)*100 = 50.0
    assert result.winner.delivery_score == 100.0
    assert result.runner_up.delivery_score == 50.0


def test_three_suppliers_weighted_blend(test_db):
    """
    3 suppliers with known values — verify exact scores match the formula.

    FurniCo:  price=0.10, days=14, rating=4.7, warranty=3
    ChairHub: price=0.08, days=7,  rating=4.2, warranty=2
    OfficePro: price=0.09, days=3,  rating=4.5, warranty=1
    """
    conn = sqlite3.connect(test_db)
    _insert_agent(conn)
    rfq_id = "rfq-blend"

    _insert_supplier(conn, "furnico", "FurniCo", rating=4.7, warranty_yrs=3.0, base_cost=0.10)
    _insert_supplier(conn, "chairhub", "ChairHub", rating=4.2, warranty_yrs=2.0, base_cost=0.08)
    _insert_supplier(conn, "officepro", "OfficePro", rating=4.5, warranty_yrs=1.0, base_cost=0.09)

    _insert_rfq(conn, rfq_id)
    _insert_quote(conn, rfq_id, "furnico",
                  unit_price=0.10, total_price=5.0,
                  delivery_days=14, warranty_yrs=3.0)
    _insert_quote(conn, rfq_id, "chairhub",
                  unit_price=0.08, total_price=4.0,
                  delivery_days=7, warranty_yrs=2.0)
    _insert_quote(conn, rfq_id, "officepro",
                  unit_price=0.09, total_price=4.5,
                  delivery_days=3, warranty_yrs=1.0)
    conn.commit()
    conn.close()

    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.compare_quotes as cq
        importlib.reload(cq)

        result = cq.compare_quotes(rfq_id)

    assert len(result.quotes_scored) == 3

    # min_price=0.08, min_days=3, max_rating=4.7, max_warranty=3.0
    # ChairHub: price=(0.08/0.08)*100=100, delivery=(3/7)*100=42.86,
    #           rating=(4.2/4.7)*100=89.36, warranty=(2/3)*100=66.67
    #     total = 100*0.40 + 42.86*0.30 + 89.36*0.20 + 66.67*0.10
    #           = 40.0 + 12.858 + 17.872 + 6.667 = 77.40 (rounded)
    chairhub = next(q for q in result.quotes_scored if q.supplier_id == "chairhub")
    assert chairhub.price_score == 100.0
    assert chairhub.delivery_score == round((3 / 7) * 100, 2)
    assert chairhub.total_score == round(
        100.0 * 0.40 + (3 / 7 * 100) * 0.30 + (4.2 / 4.7 * 100) * 0.20 + (2 / 3 * 100) * 0.10,
        2,
    )

    # OfficePro: price=(0.08/0.09)*100=88.89, delivery=(3/3)*100=100,
    #            rating=(4.5/4.7)*100=95.74, warranty=(1/3)*100=33.33
    officepro = next(q for q in result.quotes_scored if q.supplier_id == "officepro")
    assert officepro.delivery_score == 100.0
    assert officepro.total_score == round(
        (0.08 / 0.09 * 100) * 0.40 + 100.0 * 0.30 + (4.5 / 4.7 * 100) * 0.20 + (1 / 3 * 100) * 0.10,
        2,
    )

    # FurniCo: price=(0.08/0.10)*100=80, delivery=(3/14)*100=21.43,
    #          rating=(4.7/4.7)*100=100, warranty=(3/3)*100=100
    furnico = next(q for q in result.quotes_scored if q.supplier_id == "furnico")
    assert furnico.rating_score == 100.0
    assert furnico.warranty_score == 100.0


def test_no_quotes_returns_empty(test_db):
    """An RFQ with no quotes should return winner=None and empty list."""
    conn = sqlite3.connect(test_db)
    _insert_agent(conn)
    _insert_rfq(conn, "rfq-empty")
    conn.commit()
    conn.close()

    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.compare_quotes as cq
        importlib.reload(cq)

        result = cq.compare_quotes("rfq-empty")

    assert result.winner is None
    assert result.runner_up is None
    assert len(result.quotes_scored) == 0


def test_tie_scores_order_preserved(test_db):
    """Two identical quotes should both score 100.0 — first inserted wins."""
    conn = sqlite3.connect(test_db)
    _insert_agent(conn)
    rfq_id = "rfq-tie"
    _insert_supplier(conn, "sup-X", "SupX", rating=4.0, warranty_yrs=1.0)
    _insert_supplier(conn, "sup-Y", "SupY", rating=4.0, warranty_yrs=1.0)
    _insert_rfq(conn, rfq_id)
    _insert_quote(conn, rfq_id, "sup-X",
                  unit_price=100.0, total_price=5000.0,
                  delivery_days=7, warranty_yrs=1.0)
    _insert_quote(conn, rfq_id, "sup-Y",
                  unit_price=100.0, total_price=5000.0,
                  delivery_days=7, warranty_yrs=1.0)
    conn.commit()
    conn.close()

    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.compare_quotes as cq
        importlib.reload(cq)

        result = cq.compare_quotes(rfq_id)

    # Both should score identically
    assert result.winner.total_score == result.runner_up.total_score
    assert result.winner.total_score == 100.0
    # Winner is first in DB insert order (ASC by created_at)
    assert result.winner.supplier_id == "sup-X"
