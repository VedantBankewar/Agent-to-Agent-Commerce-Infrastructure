"""
demo.py — AgentTrade end-to-end procurement demo orchestrator.

One-command runner that executes the full agent-to-agent commerce lifecycle:
  DB init → seed suppliers → verify escrow → start marketplace →
  parse goal → search suppliers → broadcast RFQ → generate quotes →
  score & rank → lock escrow → print transaction trail.

Usage:
  python demo.py --goal "Buy 50 ergonomic chairs, budget 300000, by June 15"
  python demo.py --goal "Buy 100 pens, budget 5000, by May 1"
  python demo.py --skip-marketplace  (use SQLite fallback only)
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on Python path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Load .env before any other imports that read env vars
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on shell env


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH    = os.getenv("DATABASE_PATH", "db/hackathon.db")
MARKETPLACE_PORT = 8000
MARKETPLACE_URL  = f"http://localhost:{MARKETPLACE_PORT}"
BUYER_AGENT_ID   = "demo-buyer-agent"
BUYER_AGENT_NAME = "DemoProcurementBot"


# ---------------------------------------------------------------------------
# ANSI colours — terminal output formatting
# ---------------------------------------------------------------------------

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
RED     = "\033[91m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"


def banner(text: str) -> None:
    """Print a prominent section header."""
    w = 60
    print(f"\n{BOLD}{CYAN}{'═' * w}")
    print(f"  {text}")
    print(f"{'═' * w}{RESET}\n")


def step(icon: str, msg: str, **details: Any) -> None:
    """Print a pipeline step with optional key-value details."""
    print(f"  {icon}  {BOLD}{msg}{RESET}")
    for k, v in details.items():
        print(f"      {DIM}{k}: {v}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}✓  {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠  {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"  {RED}✗  {msg}{RESET}")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — Prerequisites check
# ═══════════════════════════════════════════════════════════════════════════


def check_prerequisites() -> None:
    """Verify API keys, escrow config, and Redis status."""
    banner("AGENTTRADE — DEMO STARTUP")

    # LLM key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        ok("ANTHROPIC_API_KEY set")
    else:
        warn("ANTHROPIC_API_KEY not set — LLM agent mode unavailable")

    # Escrow deploy config
    config_path = ROOT / "contracts" / "deploy_config.json"
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        ok(f"Escrow contract deployed — App ID: {config['app_id']}")
    else:
        warn("No deploy_config.json — escrow lock will be skipped")

    # Redis
    try:
        from messaging.redis_client import ping as redis_ping
        if redis_ping():
            ok("Redis connected")
        else:
            warn("Redis not running — using SQLite fallback (expected)")
    except Exception:
        warn("Redis module unavailable — using SQLite fallback")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — Database init, seed data, buyer agent registration
# ═══════════════════════════════════════════════════════════════════════════


def init_database() -> None:
    """Create tables from schema.sql if they don't exist."""
    step("🗄️", "Initializing database...")

    from db.initializedb import init_db
    init_db(DATABASE_PATH)

    # Verify tables
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    ok(f"Database ready — {len(tables)} tables: {', '.join(tables)}")


def seed_suppliers() -> None:
    """Seed FurniCo, ChairHub, OfficePro into the suppliers table (idempotent)."""
    step("🌱", "Seeding supplier data...")

    from marketplace.seed_data import SUPPLIERS

    # Check if already seeded
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM suppliers")
    count = cursor.fetchone()[0]
    conn.close()

    if count >= len(SUPPLIERS):
        ok(f"Suppliers already seeded — {count} in database")
        return

    from marketplace.seed_data import seed
    results = seed()
    ok(f"Seeded {len(results)}/{len(SUPPLIERS)} suppliers")


def ensure_buyer_agent() -> None:
    """Register the demo buyer agent in the agents table (idempotent)."""
    from utils.wallet import Wallet, save_wallet

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT agent_id FROM agents WHERE agent_id = ?",
        (BUYER_AGENT_ID,),
    )
    if cursor.fetchone() is not None:
        conn.close()
        ok(f"Buyer agent registered — {BUYER_AGENT_ID}")
        return

    # Generate wallet
    wallet = Wallet.generate()
    now = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        """
        INSERT INTO agents (agent_id, agent_type, name, wallet_addr, created_at)
        VALUES (?, 'procurement', ?, ?, ?)
        """,
        (BUYER_AGENT_ID, BUYER_AGENT_NAME, wallet.address, now),
    )
    conn.commit()
    conn.close()

    save_wallet(BUYER_AGENT_ID, wallet)
    ok(f"Buyer agent registered — {BUYER_AGENT_ID} | {wallet.address[:16]}...")
    
    # Fund the buyer agent from deployer wallet
    try:
        from utils.wallet import load_wallet, sign_and_send_txn
        deployer = load_wallet("deployer")
        print(f"    Funding buyer {wallet.address[:8]}... from deployer wallet...")
        sign_and_send_txn(deployer, wallet.address, 50000000, note="Buyer demo funding")
    except Exception as e:
        warn(f"Failed to fund buyer from deployer: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — Verify on-chain escrow contract
# ═══════════════════════════════════════════════════════════════════════════


def verify_escrow() -> dict | None:
    """Check that the deployed escrow contract is reachable on Testnet."""
    step("📋", "Checking escrow contract...")

    config_path = ROOT / "contracts" / "deploy_config.json"
    if not config_path.exists():
        warn("No deploy_config.json — will skip on-chain operations")
        return None

    with open(config_path) as f:
        config = json.load(f)
    app_id = config["app_id"]

    try:
        from utils.wallet import get_algo_client
        from contracts.interact import get_escrow_state

        client = get_algo_client()
        state = get_escrow_state(client, app_id)
        ok(
            f"Escrow live — App ID: {app_id} | "
            f"State: {state.state_name} | "
            f"Network: {config.get('network', 'testnet')}"
        )
        return config
    except Exception as exc:
        warn(f"Escrow query failed: {exc}")
        warn("On-chain operations will fail gracefully")
        return config


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — Start marketplace API (background subprocess)
# ═══════════════════════════════════════════════════════════════════════════

_marketplace_proc: subprocess.Popen | None = None


def start_marketplace() -> bool:
    """Spawn uvicorn in the background and wait until /health responds."""
    global _marketplace_proc

    step("🌐", "Starting marketplace API...")

    _marketplace_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "marketplace.registry:app",
            "--host", "127.0.0.1",
            "--port", str(MARKETPLACE_PORT),
            "--log-level", "warning",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # Poll /health for up to 10 seconds
    import urllib.request
    for _ in range(20):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(
                f"{MARKETPLACE_URL}/health", timeout=2
            ) as resp:
                if resp.status == 200:
                    ok(f"Marketplace API running — {MARKETPLACE_URL}")
                    return True
        except Exception:
            pass

    fail("Marketplace API did not start within 10s")
    if _marketplace_proc.poll() is not None:
        stderr = _marketplace_proc.stderr.read().decode() if _marketplace_proc.stderr else ""
        fail(f"Process exited: {stderr[:200]}")
    return False


def stop_marketplace() -> None:
    """Terminate the marketplace subprocess on exit."""
    global _marketplace_proc
    if _marketplace_proc is not None and _marketplace_proc.poll() is None:
        _marketplace_proc.terminate()
        try:
            _marketplace_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _marketplace_proc.kill()
        _marketplace_proc = None


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5 — Supplier quote bots (direct tool calls, no LLM required)
# ═══════════════════════════════════════════════════════════════════════════


def generate_supplier_quotes(
    rfq_id: str,
    item: str,
    quantity: int,
    category: str,
) -> int:
    """
    Simulate supplier agents responding to an RFQ.

    Instead of requiring 3 separate LLM agents, this calls the same tools
    a supplier agent would use (calculate_quote) and inserts the resulting
    quotes directly into SQLite.  This makes the demo deterministic and
    fast — no LLM latency, no Redis requirement.
    """
    step("🤖", "Supplier agents generating quotes...")

    from tools.calculate_quote import calculate_quote

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find suppliers in the matching category
    cursor.execute(
        "SELECT supplier_id, name, base_cost, margin_pct, lead_days, warranty_yrs "
        "FROM suppliers WHERE category = ?",
        (category,),
    )
    suppliers = cursor.fetchall()

    quotes_generated = 0

    for supplier in suppliers:
        sid   = supplier["supplier_id"]
        sname = supplier["name"]

        # Use the same calculate_quote tool the LLM agent would invoke
        quote = calculate_quote(sid, item, quantity, category)

        if quote is not None:
            unit_price    = quote.unit_price
            total_price   = quote.total_price
            delivery_days = quote.delivery_days
            warranty_yrs  = quote.warranty_yrs
            valid_until   = quote.valid_until
        else:
            # Fallback: compute from supplier base_cost even without inventory
            unit_price    = round(
                supplier["base_cost"] * (1 + supplier["margin_pct"] / 100), 4
            )
            total_price   = round(unit_price * quantity, 2)
            delivery_days = supplier["lead_days"]
            warranty_yrs  = supplier["warranty_yrs"]
            valid_until   = (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat()

        # Insert quote row
        quote_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO quotes
                (quote_id, rfq_id, supplier_id, unit_price, total_price,
                 delivery_days, warranty_yrs, valid_until, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                quote_id, rfq_id, sid,
                unit_price, total_price,
                delivery_days, warranty_yrs,
                valid_until, now,
            ),
        )
        quotes_generated += 1
        step(
            "  💬",
            f"{sname} quoted ${unit_price:.2f}/unit  |  "
            f"{delivery_days}d delivery  |  {warranty_yrs}yr warranty",
        )

    conn.commit()
    conn.close()

    ok(f"{quotes_generated} supplier quotes generated")
    return quotes_generated


# ═══════════════════════════════════════════════════════════════════════════
# STEPS 6-7 — Procurement pipeline (inline with milestones)
# ═══════════════════════════════════════════════════════════════════════════


def run_procurement_pipeline(goal: str) -> dict[str, Any] | None:
    """
    Execute the full procurement pipeline with live milestone output.

    Steps:
      6. Parse goal → structured RFQ fields
      7.1 Search suppliers
      7.2 Broadcast RFQ
      7.3 Supplier bots generate quotes
      7.4 Score & rank quotes
      7.5 Select winner
      7.6 Lock escrow on Algorand
    """
    banner("PROCUREMENT PIPELINE")

    # ------------------------------------------------------------------
    # 6. Parse natural-language goal
    # ------------------------------------------------------------------
    from agents.procurement_agent import parse_procurement_goal

    parsed = parse_procurement_goal(goal)
    step(
        "🎯", "Goal parsed",
        item=parsed["item"],
        quantity=parsed["quantity"],
        budget=f"{parsed['budget']:,.0f} ALGO",
        deadline=parsed["deadline"],
        category=parsed["category"],
    )
    print()

    item     = parsed["item"]
    quantity = parsed["quantity"]
    budget   = parsed["budget"]
    deadline = parsed["deadline"]
    category = parsed["category"]

    deadline_dt = datetime.strptime(deadline, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    deadline_ts = int(deadline_dt.timestamp())

    # ------------------------------------------------------------------
    # 7.1  Search suppliers
    # ------------------------------------------------------------------
    from tools.search_suppliers import search_suppliers

    suppliers = search_suppliers(category=category)
    step("📡", f"Supplier search — {len(suppliers)} found", category=category)
    for s in suppliers:
        print(
            f"      {DIM}• {s.name}  (rating {s.rating}  "
            f"base ${s.base_cost}  lead {s.lead_days}d){RESET}"
        )
    print()

    if not suppliers:
        suppliers = search_suppliers(item=item)
        step("📡", f"Fallback by item — {len(suppliers)} found")
        if not suppliers:
            fail("No suppliers found — cannot proceed")
            return None

    # ------------------------------------------------------------------
    # 7.2  Broadcast RFQ
    # ------------------------------------------------------------------
    from tools.send_rfq import send_rfq

    rfq_result = send_rfq(
        agent_id=BUYER_AGENT_ID,
        item=item,
        quantity=quantity,
        budget=budget,
        deadline=deadline,
        category=category,
        wait_for_quotes=False,   # We'll generate quotes in the next step
        timeout_seconds=0,
    )
    rfq_id = rfq_result.rfq_id
    step("📤", "RFQ broadcast to supplier network",
         rfq_id=rfq_id[:12] + "...",
         status=rfq_result.status)
    print()

    # ------------------------------------------------------------------
    # 7.3  Supplier bots respond
    # ------------------------------------------------------------------
    num_quotes = generate_supplier_quotes(rfq_id, item, quantity, category)
    print()

    if num_quotes == 0:
        fail("No supplier quotes received — pipeline halted")
        return None

    # ------------------------------------------------------------------
    # 7.4  Score & rank quotes
    # ------------------------------------------------------------------
    from tools.compare_quotes import compare_quotes

    compare_result = compare_quotes(rfq_id)
    step("📊", f"Quotes scored — {len(compare_result.quotes_scored)} evaluated")
    for q in compare_result.quotes_scored:
        crown = "👑" if q == compare_result.winner else "  "
        print(
            f"      {crown} {q.supplier_name}: "
            f"score={q.total_score:.1f}  |  "
            f"${q.unit_price:.2f}/unit  |  "
            f"{q.delivery_days}d  |  "
            f"{q.warranty_yrs}yr"
        )
    print()

    if compare_result.winner is None:
        fail("No winner — cannot proceed to escrow")
        return None

    # ------------------------------------------------------------------
    # 7.5  Winner summary
    # ------------------------------------------------------------------
    winner = compare_result.winner
    step(
        "🏆", f"Winner: {winner.supplier_name}",
        score=f"{winner.total_score:.1f}",
        unit_price=f"${winner.unit_price:.2f}",
        total=f"${winner.total_price:,.2f}",
        delivery=f"{winner.delivery_days} days",
        warranty=f"{winner.warranty_yrs} years",
    )
    print()

    # ------------------------------------------------------------------
    # 7.6  Lock escrow on Algorand Testnet
    # ------------------------------------------------------------------
    step("🔐", "Locking escrow on Algorand Testnet...")

    try:
        from tools.sign_escrow import sign_escrow

        escrow_result = sign_escrow(
            rfq_id=rfq_id,
            supplier_id=winner.supplier_id,
            item=item,
            quantity=quantity,
            unit_price=winner.unit_price,
            delivery_days=winner.delivery_days,
            warranty_yrs=winner.warranty_yrs,
            buyer_agent_id=BUYER_AGENT_ID,
            budget=budget,
            deadline_ts=deadline_ts,
        )

        ok("Escrow LOCKED on Algorand Testnet")
        step(
            "  🔗", "On-chain details",
            deal_id=escrow_result.deal_id[:12] + "...",
            deal_hash=escrow_result.deal_hash[:24] + "...",
            txid=escrow_result.txid,
            confirmed_round=escrow_result.confirmed_round,
            app_id=escrow_result.app_id,
        )

        from utils.wallet import load_wallet
        buyer_w = load_wallet(BUYER_AGENT_ID)
        supp_w = load_wallet(winner.supplier_id)

        return {
            "status":          "success",
            "rfq_id":          rfq_id,
            "deal_id":         escrow_result.deal_id,
            "supplier":        winner.supplier_name,
            "supplier_id":     winner.supplier_id,
            "item":            item,
            "quantity":        quantity,
            "unit_price":      winner.unit_price,
            "total_price":     winner.total_price,
            "delivery_days":   winner.delivery_days,
            "warranty_yrs":    winner.warranty_yrs,
            "deal_hash":       escrow_result.deal_hash,
            "buyer_address":   buyer_w.address if buyer_w else None,
            "escrow_address":  escrow_result.escrow_address,
            "supplier_address": supp_w.address if supp_w else None,
            "app_id":          escrow_result.app_id,
            "txid":            escrow_result.txid,
            "confirmed_round": escrow_result.confirmed_round,
        }

    except Exception as exc:
        import traceback
        traceback.print_exc()
        error_msg = str(exc).lower()

        # Return partial success — everything except the on-chain lock succeeded
        return {
            "status":        "escrow_pending",
            "rfq_id":        rfq_id,
            "supplier":      winner.supplier_name,
            "supplier_id":   winner.supplier_id,
            "item":          item,
            "quantity":      quantity,
            "unit_price":    winner.unit_price,
            "total_price":   winner.total_price,
            "delivery_days": winner.delivery_days,
            "warranty_yrs":  winner.warranty_yrs,
            "escrow_error":  str(exc)[:200],
        }


# ═══════════════════════════════════════════════════════════════════════════
# STEP 8 — Final transaction trail
# ═══════════════════════════════════════════════════════════════════════════


def print_transaction_trail(result: dict[str, Any], goal: str) -> None:
    """Print the coloured transaction trail summary."""
    banner("AGENTTRADE — TRANSACTION TRAIL")

    status = result.get("status", "unknown")

    print(f"  {BOLD}Goal:{RESET}   {goal}")
    print(f"  {BOLD}Status:{RESET} {status.upper()}\n")

    trail = [
        (
            "1", "RFQ Broadcast",
            f"rfq_id={result.get('rfq_id', 'N/A')[:12]}...  "
            f"item={result.get('item')}  qty={result.get('quantity')}",
        ),
        (
            "2", "Quotes Scored",
            f"winner={result.get('supplier', 'N/A')}  "
            f"price=${result.get('unit_price', 0):.2f}/unit",
        ),
        (
            "3", "Deal Agreed",
            f"total=${result.get('total_price', 0):,.2f}  "
            f"delivery={result.get('delivery_days', 'N/A')}d  "
            f"warranty={result.get('warranty_yrs', 'N/A')}yr",
        ),
    ]

    if status == "success":
        trail.append((
            "4", "Escrow LOCKED ✅",
            f"txid={result.get('txid', 'N/A')}  "
            f"round={result.get('confirmed_round', 'N/A')}  "
            f"app={result.get('app_id', 'N/A')}",
        ))
    elif status == "escrow_pending":
        trail.append((
            "4", "Escrow PENDING ⏳",
            "Buyer wallet needs ALGO — on-chain lock ready when funded",
        ))

    for num, title, detail in trail:
        if "✅" in title:
            color = GREEN
        elif "⏳" in title:
            color = YELLOW
        else:
            color = CYAN
        print(f"  {color}[{num}]{RESET}  {BOLD}{title}{RESET}")
        print(f"       {DIM}{detail}{RESET}")

    print()

    if result.get("deal_hash"):
        print(f"  {MAGENTA}Deal Hash:{RESET}  {result['deal_hash']}")
    if result.get("buyer_address"):
        print(f"  {MAGENTA}Buyer:{RESET}      {result['buyer_address']}")
    if result.get("escrow_address"):
        print(f"  {MAGENTA}Escrow:{RESET}     {result['escrow_address']}")
    if result.get("supplier_address"):
        print(f"  {MAGENTA}Supplier:{RESET}   {result['supplier_address']}")

    print(f"\n  {BOLD}{'═' * 56}{RESET}")
    print(f"  {DIM}Demo powered by Algorand × LangChain × AgentTrade{RESET}\n")


# ═══════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AgentTrade — End-to-end agent-to-agent procurement demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py --goal "Buy 50 ergonomic chairs, budget 300000, by June 15"
  python demo.py --goal "Buy 100 pens, budget 5000, by May 1"
  python demo.py --goal "Buy 10 desks, budget 50000, by August 2026"
  python demo.py --skip-marketplace   (use SQLite fallback only)
        """,
    )
    parser.add_argument(
        "--goal",
        default="Buy 50 ergonomic chairs, budget 300000, by June 15",
        help="Natural-language procurement goal (default: chairs demo)",
    )
    parser.add_argument(
        "--skip-marketplace",
        action="store_true",
        help="Skip starting the marketplace API subprocess (uses SQLite fallback)",
    )

    args = parser.parse_args()

    # Register cleanup handlers
    atexit.register(stop_marketplace)
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))

    try:
        # ── Phase 1: Prerequisites ────────────────────────────────────
        check_prerequisites()

        # ── Phase 2: Database + seed + buyer ──────────────────────────
        init_database()
        seed_suppliers()
        ensure_buyer_agent()
        print()

        # ── Phase 3: Escrow verify ────────────────────────────────────
        verify_escrow()
        print()

        # ── Phase 4: Marketplace API ──────────────────────────────────
        if not args.skip_marketplace:
            marketplace_ok = start_marketplace()
            if not marketplace_ok:
                warn("Continuing without marketplace API — SQLite fallback active")
        else:
            warn("Marketplace API skipped — using SQLite fallback")
        print()

        # ── Phases 5-7: Full procurement pipeline ─────────────────────
        result = run_procurement_pipeline(args.goal)

        # ── Phase 8: Transaction trail ────────────────────────────────
        if result:
            print_transaction_trail(result, args.goal)

        print()
        ok("Demo complete.")

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Demo interrupted.{RESET}")
    except Exception as exc:
        fail(f"Demo failed: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        stop_marketplace()


if __name__ == "__main__":
    main()
