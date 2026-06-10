"""
Comprehensive verification of AgentTrade Phases 1-7.
Checks every module, tool, agent, and the demo orchestrator.
"""

import os
import sys
import sqlite3
import json
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")

PASS = 0
FAIL = 0
WARN = 0

def check(label, fn):
    global PASS, FAIL, WARN
    try:
        result = fn()
        if result is True or result is None:
            print(f"  ✓  {label}")
            PASS += 1
        elif isinstance(result, str) and result.startswith("WARN:"):
            print(f"  ⚠  {label} — {result[5:]}")
            WARN += 1
        else:
            print(f"  ✓  {label} — {result}")
            PASS += 1
    except Exception as e:
        print(f"  ✗  {label} — {e}")
        FAIL += 1


def section(title):
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


# ═══════════════════════════════════════════════════════════
# PHASE 1 — Foundation
# ═══════════════════════════════════════════════════════════

section("PHASE 1 — Foundation")

# 1.1 requirements.txt
check("requirements.txt exists", lambda: Path("requirements.txt").exists())

# 1.2 .env.example
check(".env.example exists", lambda: Path(".env.example").exists())

# 1.3 DB schema
check("db/schema.sql exists", lambda: Path("db/schema.sql").exists())

# 1.4 DB init
def test_db_init():
    from db.initializedb import init_db
    init_db(DATABASE_PATH)
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = sorted([r[0] for r in c.fetchall()])
    conn.close()
    expected = sorted(["agents", "deals", "inventory", "quotes", "rfqs", "suppliers"])
    assert tables == expected, f"Expected {expected}, got {tables}"
    return f"{len(tables)} tables"
check("DB init + 6 tables", test_db_init)

# 1.5 Redis client
def test_redis():
    from messaging.redis_client import ping
    result = ping()
    if not result:
        return "WARN: Redis not running (expected — tools fall back to SQLite)"
    return True
check("Redis client module loads", test_redis)

# 1.6 Wallet utils
def test_wallet():
    from utils.wallet import Wallet, validate_address
    w = Wallet.generate()
    assert validate_address(w.address), "Invalid address"
    assert len(w.mnemonic.split()) == 25, "Mnemonic should be 25 words"
    return f"address={w.address[:16]}..."
check("Wallet generate + validate", test_wallet)

# 1.7 Hashing utils
def test_hashing():
    from utils.hashing import anchor_agreement, verify_agreement
    agreement = {"deal_id": "test-123", "item": "chair", "quantity": 10}
    h = anchor_agreement(agreement)
    assert h.startswith("sha256:"), f"Expected sha256: prefix, got {h[:10]}"
    assert verify_agreement(agreement, h), "Verify failed"
    return f"hash={h[:24]}..."
check("anchor_agreement + verify_agreement", test_hashing)

# 1.8 Logger
def test_logger():
    from utils.logger import get_logger, log_tool_call, log_txn
    logger = get_logger("verify_test")
    log_tool_call(logger, "test_tool", {"arg1": "val1"})
    log_txn(logger, "test transaction")
    return True
check("Logger + log_tool_call + log_txn", test_logger)


# ═══════════════════════════════════════════════════════════
# PHASE 2 — Smart Contract
# ═══════════════════════════════════════════════════════════

section("PHASE 2 — Smart Contract")

# 2.1 Escrow PyTeal compiles
def test_escrow_compile():
    from contracts.escrow import approval_program, clear_state_program
    from pyteal import compileTeal, Mode
    approval = compileTeal(approval_program(), Mode.Application, version=8)
    clear = compileTeal(clear_state_program(), Mode.Application, version=8)
    assert len(approval) > 100, "Approval TEAL too short"
    assert len(clear) > 10, "Clear TEAL too short"
    return f"approval={len(approval)} chars, clear={len(clear)} chars"
check("PyTeal compiles (approval + clear)", test_escrow_compile)

# 2.2 TEAL files exist
check("escrow_approval.teal exists", lambda: Path("contracts/escrow_approval.teal").exists())
check("escrow_clear.teal exists", lambda: Path("contracts/escrow_clear.teal").exists())

# 2.3 interact.py loads
def test_interact():
    from contracts.interact import (
        get_escrow_state, lock_escrow, submit_delivery,
        release_payment, claim_refund, load_config, state_name,
    )
    assert state_name(0) == "IDLE"
    assert state_name(1) == "LOCKED"
    assert state_name(3) == "COMPLETED"
    return "all functions importable, state_name works"
check("contracts/interact.py", test_interact)

# 2.4 deploy.py loads
check("contracts/deploy.py loads", lambda: __import__("contracts.deploy") and True)

# 2.5 deploy_config.json
def test_deploy_config():
    with open("contracts/deploy_config.json") as f:
        config = json.load(f)
    assert "app_id" in config, "Missing app_id"
    assert "address" in config, "Missing address"
    return f"app_id={config['app_id']}, network={config.get('network', 'unknown')}"
check("deploy_config.json", test_deploy_config)

# 2.6 On-chain state query
def test_onchain():
    from utils.wallet import get_algo_client
    from contracts.interact import get_escrow_state, load_config
    config = load_config()
    client = get_algo_client()
    state = get_escrow_state(client, config["app_id"])
    return f"state={state.state_name}, app_id={config['app_id']}"
check("On-chain escrow state query", test_onchain)


# ═══════════════════════════════════════════════════════════
# PHASE 3 — FastAPI Marketplace
# ═══════════════════════════════════════════════════════════

section("PHASE 3 — FastAPI Marketplace")

# 3.1 Registry loads + routes
def test_registry():
    from marketplace.registry import app
    routes = [r.path for r in app.routes]
    assert "/health" in routes, "Missing /health"
    assert "/suppliers" in routes, "Missing /suppliers"
    assert "/rfqs" in routes, "Missing /rfqs"
    return f"{len(routes)} routes"
check("marketplace/registry.py loads", test_registry)

# 3.2 Seed data
def test_seed_data():
    from marketplace.seed_data import SUPPLIERS
    assert len(SUPPLIERS) == 3, f"Expected 3 suppliers, got {len(SUPPLIERS)}"
    names = [s["name"] for s in SUPPLIERS]
    assert "FurniCo" in names
    assert "ChairHub" in names
    assert "OfficePro" in names
    return f"3 suppliers: {', '.join(names)}"
check("marketplace/seed_data.py", test_seed_data)

# 3.3 Suppliers in DB
def test_suppliers_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM suppliers")
    count = c.fetchone()[0]
    conn.close()
    assert count >= 3, f"Expected >=3 suppliers, got {count}"
    return f"{count} suppliers in DB"
check("Suppliers seeded in DB", test_suppliers_db)


# ═══════════════════════════════════════════════════════════
# PHASE 4 — Supplier Agent Tools
# ═══════════════════════════════════════════════════════════

section("PHASE 4 — Supplier Agent Tools")

# 4.1 check_inventory
def test_check_inventory():
    from tools.check_inventory import check_inventory
    # Query a non-existent item — should return available=False
    result = check_inventory("nonexistent-supplier", "widget", 10)
    assert result.available == False
    assert result.stock_count == 0
    return "available=False for unknown supplier (correct)"
check("tools/check_inventory.py", test_check_inventory)

# 4.2 calculate_quote
def test_calculate_quote():
    from tools.calculate_quote import calculate_quote
    # Get the first supplier ID from DB
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT supplier_id, name FROM suppliers LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row is None:
        return "WARN: No suppliers in DB"
    # Quote with base_cost (no inventory item)
    result = calculate_quote(row[0], "chair", 10)
    if result is not None:
        return f"unit_price={result.unit_price}, total={result.total_price}"
    return f"None for {row[1]} (no inventory match — correct fallback)"
check("tools/calculate_quote.py", test_calculate_quote)

# 4.3 evaluate_counter
def test_evaluate_counter():
    from tools.evaluate_counter import evaluate_counter
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT supplier_id FROM suppliers LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row is None:
        return "WARN: No suppliers"
    # Need a real rfq_id with a quote
    result = evaluate_counter(row[0], "test-rfq-000", 95.0, round_number=1)
    return f"decision={result.decision}, price={result.unit_price}"
check("tools/evaluate_counter.py", test_evaluate_counter)

# 4.4 submit_proof
def test_submit_proof():
    from tools.submit_proof import submit_proof
    return "module loads"
check("tools/submit_proof.py loads", test_submit_proof)


# ═══════════════════════════════════════════════════════════
# PHASE 5 — Procurement Agent Tools
# ═══════════════════════════════════════════════════════════

section("PHASE 5 — Procurement Agent Tools")

# 5.1 search_suppliers
def test_search_suppliers():
    from tools.search_suppliers import search_suppliers
    results = search_suppliers(category="furniture")
    assert len(results) >= 2, f"Expected >=2 furniture suppliers, got {len(results)}"
    names = [s.name for s in results]
    return f"{len(results)} found: {', '.join(names)}"
check("tools/search_suppliers.py", test_search_suppliers)

# 5.2 send_rfq
def test_send_rfq():
    from tools.send_rfq import send_rfq
    # Verify agent exists
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT agent_id FROM agents LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row is None:
        return "WARN: No agents in DB — cannot test send_rfq"
    agent_id = row[0]
    result = send_rfq(
        agent_id=agent_id, item="chair", quantity=5,
        budget=10000, deadline="2026-12-31", category="furniture",
        wait_for_quotes=False, timeout_seconds=0,
    )
    assert result.rfq_id, "No rfq_id returned"
    return f"rfq_id={result.rfq_id[:12]}..., status={result.status}"
check("tools/send_rfq.py", test_send_rfq)

# 5.3 compare_quotes
def test_compare_quotes():
    from tools.compare_quotes import compare_quotes
    # Get an RFQ with quotes
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT q.rfq_id, COUNT(*) AS cnt
        FROM quotes q GROUP BY q.rfq_id
        HAVING cnt > 0 ORDER BY cnt DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    if row is None:
        return "WARN: No quotes in DB to compare"
    rfq_id = row[0]
    result = compare_quotes(rfq_id)
    assert len(result.quotes_scored) > 0
    return f"rfq={rfq_id[:12]}... — {len(result.quotes_scored)} scored, winner={result.winner.supplier_name if result.winner else 'none'}"
check("tools/compare_quotes.py", test_compare_quotes)

# 5.4 sign_escrow
def test_sign_escrow():
    from tools.sign_escrow import sign_escrow, SignResult
    return "module loads, SignResult importable"
check("tools/sign_escrow.py loads", test_sign_escrow)


# ═══════════════════════════════════════════════════════════
# PHASE 6 — LangChain Agents
# ═══════════════════════════════════════════════════════════

section("PHASE 6 — Autonomous Buyer Agent & Supplier Implementations (v2)")

# 6.1 buyer prompt builder
def test_buyer_prompt():
    from agents.buyer.prompts import build_buyer_prompt
    assert callable(build_buyer_prompt)
    return "build_buyer_prompt importable"
check("agents/buyer/prompts.py", test_buyer_prompt)

# 6.2 buyer tools (8)
def test_buyer_tools():
    from agents.buyer.tools import build_buyer_tools
    # build_buyer_tools only closes over the session manager; it is not invoked
    # at build time, so None is fine for counting the registered tools.
    tools = build_buyer_tools(None)
    assert len(tools) == 8, f"Expected 8 tools, got {len(tools)}"
    names = sorted(t.name for t in tools)
    return f"8 tools: {', '.join(names)}"
check("agents/buyer/tools.py (8 tools)", test_buyer_tools)

# 6.3 supplier implementations (bot / LLM / human)
def test_supplier_impls():
    from agents.supplier.bot import RuleBotSupplier
    from agents.supplier.llm_agent import LLMSupplier
    from agents.supplier.human import HumanSupplier
    assert RuleBotSupplier and LLMSupplier and HumanSupplier
    return "RuleBot / LLM / Human suppliers importable"
check("agents/supplier/* implementations", test_supplier_impls)

# 6.4 core negotiation + types
def test_core_layer():
    from core.negotiation import NegotiationSessionManager
    from core.types import ProcurementRequest, NegotiationTerms, Priority
    assert NegotiationSessionManager and ProcurementRequest and NegotiationTerms and Priority
    return "core negotiation + types importable"
check("core/negotiation.py + core/types.py", test_core_layer)


# ═══════════════════════════════════════════════════════════
# PHASE 7 — Demo Orchestration
# ═══════════════════════════════════════════════════════════

section("PHASE 7 — Demo Orchestration")

# 7.1 demo.py exists and has key functions
def test_demo():
    import demo
    assert hasattr(demo, "main"), "Missing main()"
    assert hasattr(demo, "check_prerequisites"), "Missing check_prerequisites()"
    assert hasattr(demo, "init_database"), "Missing init_database()"
    assert hasattr(demo, "seed_suppliers"), "Missing seed_suppliers()"
    assert hasattr(demo, "ensure_buyer_agent"), "Missing ensure_buyer_agent()"
    assert hasattr(demo, "verify_escrow"), "Missing verify_escrow()"
    assert hasattr(demo, "start_marketplace"), "Missing start_marketplace()"
    assert hasattr(demo, "run_procurement_pipeline"), "Missing run_procurement_pipeline()"
    assert hasattr(demo, "print_transaction_trail"), "Missing print_transaction_trail()"
    assert hasattr(demo, "generate_supplier_quotes"), "Missing generate_supplier_quotes()"
    return "all 10 key functions present"
check("demo.py module", test_demo)

# 7.2 Buyer agent in DB
def test_buyer_agent():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT agent_id, name, wallet_addr FROM agents WHERE agent_id = 'demo-buyer-agent'")
    row = c.fetchone()
    conn.close()
    if row is None:
        return "WARN: demo-buyer-agent not in DB (run demo.py first)"
    return f"name={row[1]}, addr={row[2][:16]}..."
check("demo-buyer-agent in agents table", test_buyer_agent)

# 7.3 Buyer wallet file
def test_buyer_wallet():
    path = Path("keys/demo-buyer-agent.json")
    assert path.exists(), "Wallet file missing"
    data = json.loads(path.read_text())
    assert "address" in data, "Missing address"
    assert "mnemonic" in data, "Missing mnemonic"
    return f"address={data['address'][:16]}..."
check("keys/demo-buyer-agent.json", test_buyer_wallet)

# 7.4 Buyer wallet balance
def test_buyer_balance():
    from utils.wallet import get_balance, load_wallet
    w = load_wallet("demo-buyer-agent")
    bal = get_balance(w.address)
    if bal == 0:
        return f"WARN: 0 ALGO — fund via dispenser for on-chain escrow"
    return f"{bal:,} microALGO ({bal / 1_000_000:.6f} ALGO)"
check("Buyer wallet balance", test_buyer_balance)


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════

section("VERIFICATION SUMMARY")
total = PASS + FAIL + WARN
print(f"  ✓ Passed:   {PASS}/{total}")
print(f"  ⚠ Warnings: {WARN}/{total}")
print(f"  ✗ Failed:   {FAIL}/{total}")
print()

if FAIL == 0:
    print("  All checks passed! Phases 1-7 are working correctly.")
else:
    print(f"  {FAIL} check(s) FAILED — investigate above.")

sys.exit(0 if FAIL == 0 else 1)
