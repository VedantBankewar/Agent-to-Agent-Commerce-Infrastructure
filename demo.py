"""
demo.py — AgentTrade v2 autonomous procurement demo.

Runs the full autonomous buyer agent that discovers suppliers, negotiates
deeply (5-7 rounds, multi-variable), and locks Algorand escrow — all
driven by an LLM making every decision.

Usage:
  python demo.py --item "Ergonomic Office Chair" --quantity 50 --budget 15000 --priority balanced
  python demo.py --item "Ballpoint Pen" --quantity 100 --budget 500 --priority cost
  python demo.py --goal "Buy 50 chairs budget 15000"  # Legacy mode (parsed to fields)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
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
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH    = os.getenv("DATABASE_PATH", "db/hackathon.db")
BUYER_AGENT_ID   = "demo-buyer-agent"
BUYER_AGENT_NAME = "DemoProcurementBot"

# ---------------------------------------------------------------------------
# ANSI colours
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
    print(f"\n{BOLD}{CYAN}{'=' * w}")
    print(f"  {text}")
    print(f"{'=' * w}{RESET}\n")


def step(icon: str, msg: str, **details: Any) -> None:
    """Print a pipeline step with optional key-value details."""
    print(f"  {icon}  {BOLD}{msg}{RESET}")
    for k, v in details.items():
        print(f"      {DIM}{k}: {v}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]  {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[WARN]  {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"  {RED}[FAIL]  {msg}{RESET}")


# =========================================================================
# STEP 1 — Prerequisites check
# =========================================================================

def check_prerequisites() -> None:
    """Verify API keys, escrow config, and Redis status."""
    banner("AGENTTRADE v2 — AUTONOMOUS AGENT DEMO")

    # LLM key — check all supported providers
    llm_providers = [
        ("DO_AI_API_KEY", "DigitalOcean GenAI"),
        ("GROQ_API_KEY", "Groq"),
        ("GOOGLE_API_KEY", "Google Gemini"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("OPENAI_API_KEY", "OpenAI"),
    ]
    found_provider = None
    for env_var, name in llm_providers:
        if os.getenv(env_var):
            found_provider = name
            break
    if found_provider:
        ok(f"LLM provider: {found_provider}")
    else:
        fail("No LLM API key — set DO_AI_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY")
        sys.exit(1)

    # Escrow deploy config
    config_path = ROOT / "contracts" / "deploy_config.json"
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        ok(f"Escrow contract deployed — App ID: {config['app_id']}")
    else:
        warn("No deploy_config.json — escrow lock will fail")

    # Redis
    try:
        from messaging.redis_client import ping as redis_ping
        if redis_ping():
            ok("Redis connected")
        else:
            warn("Redis not running — using SQLite fallback")
    except Exception:
        warn("Redis module unavailable — using SQLite fallback")


# =========================================================================
# STEP 2 — Database init, seed data, buyer agent registration
# =========================================================================

def init_database() -> None:
    """Create tables from schema.sql if they don't exist."""
    step("DB", "Initializing database...")
    from db.initializedb import init_db
    init_db(DATABASE_PATH)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    ok(f"Database ready — {len(tables)} tables: {', '.join(tables)}")


def seed_suppliers() -> None:
    """Seed suppliers into the database (idempotent)."""
    step("SEED", "Seeding supplier data...")
    from marketplace.seed_data import SUPPLIERS

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
    """Register the demo buyer agent, REUSING a persistent wallet across runs.

    server.py wipes the DB each run; if we minted a fresh wallet every time, the
    buyer's USDC (funded from the deployer) would be stranded in the previous
    run's wallet and the deployer would run dry. So we reuse keys/{BUYER}.json if
    it exists — the address (and its USDC opt-in/balance) carries over.
    """
    from utils.wallet import Wallet, save_wallet, get_supplier_wallet

    # Reuse the persistent buyer wallet if present; only mint one the first time.
    wallet = get_supplier_wallet(BUYER_AGENT_ID)
    if wallet is None:
        wallet = Wallet.generate()
        save_wallet(BUYER_AGENT_ID, wallet)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT agent_id FROM agents WHERE agent_id = ?", (BUYER_AGENT_ID,))
    if cursor.fetchone() is None:
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO agents (agent_id, agent_type, name, wallet_addr, created_at) VALUES (?, 'procurement', ?, ?, ?)",
            (BUYER_AGENT_ID, BUYER_AGENT_NAME, wallet.address, now),
        )
        conn.commit()
    conn.close()
    ok(f"Buyer agent ready — {BUYER_AGENT_ID} | {wallet.address[:16]}...")

    # Top up ALGO only when low (fees), so we don't re-drain the deployer each run.
    try:
        from utils.wallet import load_wallet, get_balance, sign_and_send_txn
        if get_balance(wallet.address) < 1_000_000:  # < 1 ALGO
            deployer = load_wallet("deployer")
            print(f"    Funding buyer {wallet.address[:8]}... from deployer wallet...")
            sign_and_send_txn(deployer, wallet.address, 25_000_000, note="Buyer demo funding")
    except Exception as e:
        warn(f"Failed to fund buyer from deployer: {e}")


def ensure_buyer_usdc(deploy_config: dict | None) -> None:
    """Ensure the buyer wallet has USDC for escrow locking."""
    if not deploy_config:
        return
    usdc_id = deploy_config.get("usdc_asset_id")
    if not usdc_id:
        return

    try:
        import os
        from algosdk.v2client.algod import AlgodClient
        from algosdk.transaction import AssetTransferTxn, wait_for_confirmation
        from algosdk import mnemonic as mn
        from algosdk.account import address_from_private_key

        # Get buyer address
        conn = sqlite3.connect(DATABASE_PATH)
        row = conn.execute(
            "SELECT wallet_addr FROM agents WHERE agent_id = ?", (BUYER_AGENT_ID,)
        ).fetchone()
        conn.close()
        if not row:
            return
        buyer_addr = row[0]

        client = AlgodClient(
            "", os.getenv("ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"),
            headers={"User-Agent": "algosdk"},
        )
        info = client.account_info(buyer_addr)
        for asset in info.get("assets", []):
            if asset["asset-id"] == usdc_id and asset["amount"] > 0:
                ok(f"Buyer has {asset['amount']/1_000_000:,.2f} USDC")
                return

        # Buyer has 0 USDC — fund from deployer
        creator_mn = os.getenv("ALGORAND_CREATOR_MNEMONIC", "").strip('"')
        creator_sk = mn.to_private_key(creator_mn)
        creator_addr = address_from_private_key(creator_sk)

        # Check deployer's USDC balance
        deployer_info = client.account_info(creator_addr)
        deployer_usdc = 0
        for asset in deployer_info.get("assets", []):
            if asset["asset-id"] == usdc_id:
                deployer_usdc = asset["amount"]
                break

        if deployer_usdc == 0:
            warn(f"Deployer has 0 USDC. Fund {creator_addr} with testnet USDC first.")
            return

        # Opt buyer into USDC if needed
        opted_in = any(a["asset-id"] == usdc_id for a in info.get("assets", []))
        if not opted_in:
            from utils.wallet import load_wallet
            buyer_wallet = load_wallet(BUYER_AGENT_ID)
            sp = client.suggested_params()
            opt_txn = AssetTransferTxn(
                sender=buyer_addr, sp=sp, receiver=buyer_addr, amt=0, index=usdc_id,
            )
            signed = opt_txn.sign(buyer_wallet.private_key)
            txid = client.send_transaction(signed)
            wait_for_confirmation(client, txid, 10)

        # Transfer available USDC to buyer (keep 1 USDC reserve for deployer)
        reserve = 1_000_000  # 1 USDC in micro-USDC
        transfer_amount = max(0, deployer_usdc - reserve)
        if transfer_amount == 0:
            warn("Deployer USDC balance too low to fund buyer.")
            return

        sp = client.suggested_params()
        txn = AssetTransferTxn(
            sender=creator_addr, sp=sp, receiver=buyer_addr, amt=transfer_amount, index=usdc_id,
        )
        signed = txn.sign(creator_sk)
        txid = client.send_transaction(signed)
        wait_for_confirmation(client, txid, 10)
        ok(f"Funded buyer with {transfer_amount/1_000_000:,.2f} USDC")
    except Exception as e:
        warn(f"Failed to fund buyer USDC: {e}")


def verify_escrow() -> dict | None:
    """Check that the deployed escrow contract is reachable on Testnet."""
    step("ESCROW", "Checking escrow contract...")
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
        ok(f"Escrow live — App ID: {app_id} | State: {state.state_name}")
        return config
    except Exception as exc:
        warn(f"Escrow query failed: {exc}")
        return config


# =========================================================================
# STEP 3 — Run autonomous buyer agent
# =========================================================================

def run_autonomous_agent(
    item: str,
    category: str,
    quantity: int,
    budget_usd: float,
    deadline: str,
    target_price_usd: float | None,
    min_warranty_yrs: float,
    priority: str,
    requirements: str,
) -> None:
    """Run the autonomous LangGraph buyer agent."""
    from core.types import ProcurementRequest, Priority
    from core.events import EventBus
    from agents.buyer.agent import run_buyer_agent

    # Set up live event printing
    def print_event(event_type: str, data: dict) -> None:
        if event_type == "agent_started":
            banner("AUTONOMOUS PROCUREMENT AGENT DEPLOYED")
            step("AGENT", f"Buyer: {data.get('buyer_id', '')}")
            req = data.get("request", {})
            step("", f"Item: {req.get('item', '')} x {req.get('quantity', '')}")
            step("", f"Budget: ${req.get('budget_usd', 0):,.2f} USD")
            step("", f"Priority: {req.get('priority', 'balanced')}")

        elif event_type == "suppliers_discovered":
            print(f"\n  {CYAN}=> {data['count']} SUPPLIERS DISCOVERED{RESET}")
            for s in data.get("suppliers", []):
                print(f"      {DIM}{s['name']} (rating {s['rating']}){RESET}")

        elif event_type == "quote_received":
            terms = data.get("terms", {})
            print(
                f"\n  {BLUE}[QUOTE]{RESET} {data.get('supplier_name', '')}: "
                f"${terms.get('unit_price_usd', 0):.2f}/unit | "
                f"{terms.get('delivery_days', 0)}d | "
                f"{terms.get('warranty_yrs', 0)}yr warranty | "
                f"Score: {data.get('score', 0):.1f}"
            )

        elif event_type == "counter_sent":
            terms = data.get("proposed_terms", {})
            print(
                f"\n  {MAGENTA}[COUNTER ->]{RESET} To {data.get('supplier_id', '')[:20]} "
                f"Round {data.get('round', 0)}: "
                f"${terms.get('unit_price_usd', 0):.2f}/unit | "
                f"{terms.get('delivery_days', 0)}d | "
                f"{terms.get('warranty_yrs', 0)}yr"
            )
            if data.get("reasoning"):
                print(f"      {DIM}{data['reasoning'][:100]}{RESET}")

        elif event_type == "counter_received":
            terms = data.get("response_terms", {})
            decision = data.get("decision", "?")
            color = GREEN if decision == "accept" else (YELLOW if decision == "counter" else RED)
            print(
                f"  {color}[<- {decision.upper()}]{RESET} From {data.get('supplier_id', '')[:20]} "
                f"Round {data.get('round', 0)}"
            )
            if terms:
                print(
                    f"      ${terms.get('unit_price_usd', 0):.2f}/unit | "
                    f"{terms.get('delivery_days', 0)}d | "
                    f"{terms.get('warranty_yrs', 0)}yr"
                )
            if data.get("supplier_message"):
                print(f"      {DIM}\"{data['supplier_message'][:120]}\"{RESET}")

        elif event_type == "offer_accepted":
            terms = data.get("final_terms", {})
            print(f"\n  {GREEN}{BOLD}=> OFFER ACCEPTED — {data.get('supplier_name', '')}{RESET}")
            if terms:
                print(
                    f"      ${terms.get('unit_price_usd', 0):.2f}/unit x "
                    f"{terms.get('quantity', 0)} = "
                    f"${terms.get('total_usd', 0):,.2f}"
                )

        elif event_type == "supplier_rejected":
            print(f"  {RED}[REJECTED]{RESET} {data.get('supplier_name', '')}: {data.get('reason', '')[:80]}")

        elif event_type == "escrow_locked":
            banner("ESCROW LOCKED ON ALGORAND TESTNET")
            step("DEAL", f"Deal ID: {data.get('deal_id', '')}")
            step("", f"TX ID: {data.get('txid', 'N/A')}")
            step("", f"Confirmed Round: {data.get('confirmed_round', 'N/A')}")
            step("", f"Amount: ${data.get('amount_usd', 0):,.2f} USDC")
            step("", f"Deal Hash: {data.get('deal_hash', '')}")

        elif event_type == "agent_thinking":
            thought = data.get("thought", "")
            if thought:
                print(f"  {DIM}[THINKING] {thought[:150]}{RESET}")

        elif event_type == "agent_error":
            print(f"  {RED}[ERROR] {data.get('error_type', '')}: {data.get('message', '')}{RESET}")

    EventBus.subscribe(print_event)

    # Build ProcurementRequest
    request = ProcurementRequest(
        item=item,
        category=category,
        quantity=quantity,
        budget_usd=budget_usd,
        deadline=deadline,
        target_price_usd=target_price_usd,
        min_warranty_yrs=min_warranty_yrs,
        priority=Priority(priority),
        requirements=requirements,
    )

    # Run the agent
    context = run_buyer_agent(BUYER_AGENT_ID, request)

    EventBus.clear()

    # Print summary
    banner("PROCUREMENT SUMMARY")
    print(f"  Deal Phase: {context.deal_phase.value}")
    print(f"  Suppliers Contacted: {len(context.negotiations)}")

    for sid, state in context.negotiations.items():
        status_color = GREEN if state.phase.value == "accepted" else (RED if state.phase.value == "rejected" else YELLOW)
        print(f"    {status_color}{state.supplier_name}: {state.phase.value} (round {state.current_round}){RESET}")

    if context.deal_id:
        print(f"\n  {GREEN}{BOLD}Deal ID: {context.deal_id}{RESET}")
        print(f"  Settlement: USDC (1:1 with USD)")

        # Show on-chain verification addresses
        try:
            config_path = ROOT / "contracts" / "deploy_config.json"
            if config_path.exists():
                with open(config_path) as f:
                    deploy_cfg = json.load(f)
                escrow_addr = deploy_cfg.get("address", "N/A")
                app_id = deploy_cfg.get("app_id", "N/A")
                usdc_asa = deploy_cfg.get("usdc_asset_id", "N/A")
            else:
                escrow_addr = app_id = usdc_asa = "N/A"

            # Buyer address
            conn = sqlite3.connect(DATABASE_PATH)
            buyer_row = conn.execute(
                "SELECT wallet_addr FROM agents WHERE agent_id = ?", (BUYER_AGENT_ID,)
            ).fetchone()
            buyer_addr = buyer_row[0] if buyer_row else "N/A"

            # Supplier address
            winner_id = None
            for sid, state in context.negotiations.items():
                if state.phase.value == "accepted":
                    winner_id = sid
                    break
            supplier_addr = "N/A"
            if winner_id:
                sup_row = conn.execute(
                    "SELECT wallet_addr FROM suppliers WHERE supplier_id = ?", (winner_id,)
                ).fetchone()
                supplier_addr = sup_row[0] if sup_row else "N/A"
            conn.close()

            banner("ON-CHAIN VERIFICATION")
            print(f"  {CYAN}Escrow App ID:{RESET}    {app_id}")
            print(f"  {CYAN}USDC ASA ID:{RESET}      {usdc_asa}")
            print(f"  {CYAN}Buyer Address:{RESET}     {buyer_addr}")
            print(f"  {CYAN}Supplier Address:{RESET}  {supplier_addr}")
            print(f"  {CYAN}Escrow Address:{RESET}    {escrow_addr}")
            print()
            print(f"  {DIM}Verify on Pera Explorer / AlgoExplorer:{RESET}")
            print(f"    {DIM}https://explorer.perawallet.app/application/{app_id}/?network=testnet{RESET}")
            print(f"    {DIM}https://explorer.perawallet.app/address/{buyer_addr}/?network=testnet{RESET}")
            print(f"    {DIM}https://explorer.perawallet.app/address/{supplier_addr}/?network=testnet{RESET}")
            print(f"    {DIM}https://explorer.perawallet.app/address/{escrow_addr}/?network=testnet{RESET}")
        except Exception as e:
            print(f"  {DIM}(Could not fetch verification addresses: {e}){RESET}")

    elif context.deal_phase.value == "failed":
        print(f"\n  {RED}Agent could not complete procurement.{RESET}")


# =========================================================================
# Legacy goal parsing (backward compat)
# =========================================================================

def parse_legacy_goal(goal: str) -> dict:
    """Parse a free-text goal string into structured fields (best effort)."""
    import re
    result = {
        "item": "Office Chair",
        "category": "furniture",
        "quantity": 50,
        "budget_usd": 15000.0,
    }

    qty_match = re.search(r'(\d+)\s+(\w[\w\s]*?)(?:,|\s+budget)', goal, re.IGNORECASE)
    if qty_match:
        result["quantity"] = int(qty_match.group(1))
        result["item"] = qty_match.group(2).strip()

    budget_match = re.search(r'budget\s+(\d[\d,]*)', goal, re.IGNORECASE)
    if budget_match:
        result["budget_usd"] = float(budget_match.group(1).replace(",", ""))

    # Category inference
    item_lower = result["item"].lower()
    if any(w in item_lower for w in ("chair", "desk", "table", "cabinet", "shelf", "furni")):
        result["category"] = "furniture"
    elif any(w in item_lower for w in ("pen", "paper", "staple", "folder", "binder")):
        result["category"] = "office_supplies"
    elif any(w in item_lower for w in ("laptop", "monitor", "keyboard", "mouse", "cable")):
        result["category"] = "electronics"
    else:
        result["category"] = "general"

    return result


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="AgentTrade v2 — Autonomous Procurement Demo")

    # Structured args
    parser.add_argument("--item", default=None, help="Product name")
    parser.add_argument("--category", default=None, choices=["furniture", "office_supplies", "electronics", "general"])
    parser.add_argument("--quantity", type=int, default=None)
    parser.add_argument("--budget", type=float, default=None, help="Max budget in USD")
    parser.add_argument("--deadline", default=None, help="ISO date (defaults to +30d)")
    parser.add_argument("--target-price", type=float, default=None, help="Target USD per unit")
    parser.add_argument("--min-warranty", type=float, default=1.0, help="Min warranty years")
    parser.add_argument("--priority", choices=["cost", "speed", "quality", "balanced"], default="balanced")
    parser.add_argument("--requirements", default="", help="Special requirements")

    # Legacy mode
    parser.add_argument("--goal", default=None, help="Legacy free-text goal (parsed to fields)")

    args = parser.parse_args()

    # Resolve fields
    if args.goal and not args.item:
        parsed = parse_legacy_goal(args.goal)
        item = parsed["item"]
        category = parsed["category"]
        quantity = parsed["quantity"]
        budget_usd = parsed["budget_usd"]
    else:
        item = args.item or "Ergonomic Office Chair"
        category = args.category or "furniture"
        quantity = args.quantity or 50
        budget_usd = args.budget or 15000.0

    deadline = args.deadline or (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    target_price = args.target_price
    min_warranty = args.min_warranty
    priority = args.priority
    requirements = args.requirements

    # Run pipeline
    check_prerequisites()
    init_database()
    seed_suppliers()
    ensure_buyer_agent()
    deploy_config = verify_escrow()
    ensure_buyer_usdc(deploy_config)

    run_autonomous_agent(
        item=item,
        category=category,
        quantity=quantity,
        budget_usd=budget_usd,
        deadline=deadline,
        target_price_usd=target_price,
        min_warranty_yrs=min_warranty,
        priority=priority,
        requirements=requirements,
    )


if __name__ == "__main__":
    main()
