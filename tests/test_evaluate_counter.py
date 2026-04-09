"""
test_evaluate_counter — Unit tests for the negotiation round limit logic.

Verifies all 5 decision branches in evaluate_counter():
  1. Accept (at or above initial)
  2. Counter round 1 (meet halfway)
  3. Counter round 2 (hold firm)
  4. Reject (below price floor)
  5. Reject (round 3+ exceeded)
  6. Supplier not found
  7. No quote found

All tests use an isolated temp SQLite DB.
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

SCHEMA_FILE = ROOT / "db" / "schema.sql"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db(tmp_path):
    """Create a fresh test DB with schema and a standard supplier + quote."""
    db_path = str(tmp_path / "test_negotiate.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_FILE.read_text())

    now = datetime.now(timezone.utc).isoformat()
    valid_until = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    # Insert a test buyer agent (needed for RFQ FK)
    conn.execute(
        "INSERT INTO agents (agent_id, agent_type, name, wallet_addr, created_at) "
        "VALUES ('test-buyer', 'procurement', 'TestBuyer', 'ADDR_BUYER', ?)",
        (now,),
    )

    # Insert standard test supplier:
    #   min_price=80.0 (floor), base_cost=80.0, margin_pct=25% → initial~100
    #   lead_days=7, warranty_yrs=2.0
    conn.execute(
        "INSERT INTO suppliers "
        "(supplier_id, name, category, wallet_addr, rating, min_price, base_cost, "
        "margin_pct, lead_days, warranty_yrs, created_at) "
        "VALUES ('sup-test', 'TestSupplier', 'furniture', 'ADDR_SUP', 4.5, "
        "80.0, 80.0, 25.0, 7, 2.0, ?)",
        (now,),
    )

    # Insert RFQ
    conn.execute(
        "INSERT INTO rfqs "
        "(rfq_id, agent_id, item, quantity, budget, deadline, category, status, created_at) "
        "VALUES ('rfq-neg', 'test-buyer', 'chairs', 50, 10000, '2026-06-15', "
        "'furniture', 'open', ?)",
        (now,),
    )

    # Insert a quote at unit_price=100.0 (this is the "initial_price")
    conn.execute(
        "INSERT INTO quotes "
        "(quote_id, rfq_id, supplier_id, unit_price, total_price, delivery_days, "
        "warranty_yrs, valid_until, status, created_at) "
        "VALUES (?, 'rfq-neg', 'sup-test', 100.0, 5000.0, 7, 2.0, ?, 'pending', ?)",
        (str(uuid.uuid4()), valid_until, now),
    )

    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Test: Accept — offer at or above initial price
# ---------------------------------------------------------------------------

def test_accept_at_or_above_initial(test_db):
    """Offer >= initial_price (100.0) → always accept."""
    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.evaluate_counter as ec
        importlib.reload(ec)

        result = ec.evaluate_counter(
            supplier_id="sup-test",
            rfq_id="rfq-neg",
            counter_price=105.0,
            round_number=1,
        )

    assert result.decision == "accept"
    assert result.unit_price == 105.0
    assert "accepted" in result.message.lower()


# ---------------------------------------------------------------------------
# Test: Counter round 1 — meet halfway
# ---------------------------------------------------------------------------

def test_counter_round1_meet_halfway(test_db):
    """
    Offer in acceptable band (>= max_acceptable) at round 1 → counter at halfway.

    max_acceptable = 100.0 * (1 - 0.08) = 92.0
    counter_price = 95.0 (>= 92.0)
    halfway = (95.0 + 92.0) / 2 = 93.5
    """
    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.evaluate_counter as ec
        importlib.reload(ec)

        result = ec.evaluate_counter(
            supplier_id="sup-test",
            rfq_id="rfq-neg",
            counter_price=95.0,
            round_number=1,
        )

    assert result.decision == "counter"
    assert result.unit_price == 93.5
    assert result.round == 1
    assert "halfway" in result.message.lower()


# ---------------------------------------------------------------------------
# Test: Counter round 2 — hold firm at max acceptable
# ---------------------------------------------------------------------------

def test_counter_round2_hold_firm(test_db):
    """
    Same price (95.0 >= 92.0) at round 2 → counter at max_acceptable=92.0.
    """
    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.evaluate_counter as ec
        importlib.reload(ec)

        result = ec.evaluate_counter(
            supplier_id="sup-test",
            rfq_id="rfq-neg",
            counter_price=95.0,
            round_number=2,
        )

    assert result.decision == "counter"
    assert result.unit_price == 92.0
    assert result.round == 2
    assert "firm" in result.message.lower()


# ---------------------------------------------------------------------------
# Test: Reject — below price floor
# ---------------------------------------------------------------------------

def test_reject_below_price_floor(test_db):
    """Offer < price_floor (80.0) → always reject regardless of round."""
    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.evaluate_counter as ec
        importlib.reload(ec)

        result = ec.evaluate_counter(
            supplier_id="sup-test",
            rfq_id="rfq-neg",
            counter_price=75.0,
            round_number=1,
        )

    assert result.decision == "reject"
    assert result.unit_price == 80.0  # Returns floor as guidance
    assert "below price floor" in result.message.lower()


# ---------------------------------------------------------------------------
# Test: Reject — round 3 exceeded
# ---------------------------------------------------------------------------

def test_reject_round3_exceeded(test_db):
    """
    Offer below max_acceptable (85.0 < 92.0) at round 3 → reject.
    MAX_NEGOTIATION_ROUNDS = 2, so round 3 > 2 → rejection triggers.
    """
    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.evaluate_counter as ec
        importlib.reload(ec)

        result = ec.evaluate_counter(
            supplier_id="sup-test",
            rfq_id="rfq-neg",
            counter_price=85.0,
            round_number=3,
        )

    assert result.decision == "reject"
    assert "max negotiation rounds" in result.message.lower()
    assert result.round == 3


# ---------------------------------------------------------------------------
# Test: Supplier not found
# ---------------------------------------------------------------------------

def test_supplier_not_found(test_db):
    """Unknown supplier_id → reject with 'not found' message."""
    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.evaluate_counter as ec
        importlib.reload(ec)

        result = ec.evaluate_counter(
            supplier_id="sup-nonexistent",
            rfq_id="rfq-neg",
            counter_price=100.0,
            round_number=1,
        )

    assert result.decision == "reject"
    assert "not found" in result.message.lower()


# ---------------------------------------------------------------------------
# Test: No quote found for the RFQ
# ---------------------------------------------------------------------------

def test_no_quote_found(test_db):
    """Supplier exists but has no quote for this RFQ → reject."""
    # Add a different supplier with no quote
    conn = sqlite3.connect(test_db)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO suppliers "
        "(supplier_id, name, category, wallet_addr, rating, min_price, base_cost, "
        "margin_pct, lead_days, warranty_yrs, created_at) "
        "VALUES ('sup-noquote', 'NoQuoteSupplier', 'furniture', 'ADDR_NQ', 4.0, "
        "80.0, 80.0, 20.0, 7, 1.0, ?)",
        (now,),
    )
    conn.commit()
    conn.close()

    with mock.patch.dict(os.environ, {"DATABASE_PATH": test_db}):
        import importlib
        import tools.evaluate_counter as ec
        importlib.reload(ec)

        result = ec.evaluate_counter(
            supplier_id="sup-noquote",
            rfq_id="rfq-neg",
            counter_price=100.0,
            round_number=1,
        )

    assert result.decision == "reject"
    assert "no quote found" in result.message.lower()
