"""
sign_escrow — Procurement agent tool.
Build the agreement dict, anchor its hash on Algorand via the escrow contract,
persist the agreement JSON, and record the deal in SQLite.

Settlement uses USDC (ASA) instead of native ALGO. All prices in USD/USDC (1:1).
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from utils.hashing import anchor_agreement
from utils.logger import get_logger, log_tool_call, log_txn
from utils.wallet import get_algo_client, load_wallet


DATABASE_PATH    = os.getenv("DATABASE_PATH",       "db/hackathon.db")
AGREEMENTS_DIR   = os.getenv("AGREEMENTS_DIR",      "agreements")
CONFIG_FILE      = "contracts/deploy_config.json"


@dataclass
class SignResult:
    deal_id: str
    rfq_id: str
    supplier_id: str
    item: str
    quantity: int
    unit_price: float
    total_price: float
    delivery_days: int
    warranty_yrs: float
    deal_hash: str
    escrow_address: str
    app_id: int
    txid: str | None
    confirmed_round: int | None
    status: str


def sign_escrow(
    rfq_id: str,
    supplier_id: str,
    item: str,
    quantity: int,
    unit_price: float,
    delivery_days: int,
    warranty_yrs: float,
    buyer_agent_id: str,
    budget: float,
    deadline_ts: int,
) -> SignResult:
    """
    Lock buyer funds in the escrow contract and record the agreement.

    Workflow:
      1. Load buyer wallet and escrow config (app_id, address)
      2. Build agreement dict and compute deal_hash via anchor_agreement()
      3. Call lock_escrow() on-chain (payment + app call group transaction)
      4. Save full agreement JSON to agreements/{deal_id}.json
      5. Insert deal record into SQLite

    Args:
        rfq_id:         The RFQ this deal is for.
        supplier_id:   Winning supplier's ID.
        item:          Item being procured.
        quantity:      Units being procured.
        unit_price:    Agreed unit price (USD/USDC).
        delivery_days: Promised delivery time.
        warranty_yrs:  Warranty period.
        buyer_agent_id:Buyer's agent ID (used to load wallet).
        budget:        Original budget in USD (for record).
        deadline_ts:   Escrow deadline as Unix timestamp (seconds).

    Returns:
        SignResult with deal_id, on-chain tx details, and agreement hash.
    """
    logger = get_logger("sign_escrow")

    log_tool_call(
        logger,
        "sign_escrow",
        {
            "rfq_id": rfq_id,
            "supplier_id": supplier_id,
            "item": item,
            "quantity": quantity,
            "unit_price": unit_price,
        },
    )

    # -------------------------------------------------------------------------
    # Step 1: Load wallets and escrow config
    # -------------------------------------------------------------------------
    buyer_wallet = load_wallet(buyer_agent_id)

    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        raise FileNotFoundError(
            f"{CONFIG_FILE} not found. Deploy the escrow contract first."
        )
    with open(config_path) as f:
        config = json.load(f)
    app_id = config["app_id"]
    escrow_address = config["address"]

    # Load supplier wallet address from SQLite
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT wallet_addr FROM suppliers WHERE supplier_id = ?",
        (supplier_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise ValueError(f"Supplier {supplier_id} not found in database.")
    supplier_addr = row["wallet_addr"]

    # -------------------------------------------------------------------------
    # Step 2: Build agreement dict and anchor hash
    # -------------------------------------------------------------------------
    deal_id = str(uuid.uuid4())
    total_price = round(unit_price * quantity, 2)

    agreement = {
        "deal_id":       deal_id,
        "rfq_id":        rfq_id,
        "supplier_id":  supplier_id,
        "buyer_agent_id": buyer_agent_id,
        "item":          item,
        "quantity":      quantity,
        "unit_price":    unit_price,
        "total_price":   total_price,
        "delivery_days": delivery_days,
        "warranty_yrs":  warranty_yrs,
        "budget":        budget,
        "deadline_ts":   deadline_ts,
        "agreed_at":     datetime.now(timezone.utc).isoformat(),
    }

    deal_hash = anchor_agreement(agreement)
    logger.info("Agreement anchored", extra={"deal_id": deal_id, "deal_hash": deal_hash})

    # -------------------------------------------------------------------------
    # Step 3: Call lock_escrow on-chain (USDC ASA transfer)
    # -------------------------------------------------------------------------
    amount_micro_usdc = int(total_price * 1_000_000)  # Convert USD → micro-USDC (6 decimals)

    # Load USDC ASA ID from deploy config
    usdc_asset_id = config.get("usdc_asset_id", 0)
    if not usdc_asset_id:
        raise ValueError("USDC asset ID not found in deploy config. Run deploy.py first.")

    client = get_algo_client()

    # Ensure buyer is opted into USDC ASA
    try:
        account_info = client.account_info(buyer_wallet.address)
        opted_in = any(
            a.get("asset-id") == usdc_asset_id
            for a in account_info.get("assets", [])
        )
        if not opted_in:
            from algosdk.transaction import AssetTransferTxn, wait_for_confirmation
            sp = client.suggested_params()
            optin_txn = AssetTransferTxn(
                sender=buyer_wallet.address, sp=sp,
                receiver=buyer_wallet.address, amt=0, index=usdc_asset_id,
            )
            signed = optin_txn.sign(buyer_wallet.private_key)
            txid = client.send_transaction(signed)
            wait_for_confirmation(client, txid, 30)
            logger.info("Buyer opted into USDC ASA", extra={"asset_id": usdc_asset_id})
    except Exception as e:
        logger.warning("USDC opt-in check failed", extra={"error": str(e)})

    from contracts.interact import lock_escrow

    try:
        result = lock_escrow(
            client=client,
            buyer_address=buyer_wallet.address,
            buyer_sk=buyer_wallet.private_key,
            app_id=app_id,
            seller_address=supplier_addr,
            deal_hash=deal_hash,
            amount_micro_usdc=amount_micro_usdc,
            deadline_ts=deadline_ts,
            usdc_asset_id=usdc_asset_id,
        )
        log_txn(
            logger,
            result["txid"],
            deal_id=deal_id,
            amount=amount_micro_usdc,
            confirmed=result["confirmed"],
        )
        txid = result["txid"]
        confirmed_round = result["confirmed"]
        status = "locked"
    except Exception as exc:
        logger.error("Escrow lock failed", extra={"deal_id": deal_id, "error": str(exc)})
        raise

    # -------------------------------------------------------------------------
    # Step 4: Persist agreement JSON
    # -------------------------------------------------------------------------
    agreements_dir = Path(AGREEMENTS_DIR)
    agreements_dir.mkdir(exist_ok=True)
    agreement_path = agreements_dir / f"{deal_id}.json"
    with open(agreement_path, "w") as f:
        json.dump(agreement, f, indent=2)
    logger.info("Agreement saved", extra={"deal_id": deal_id, "path": str(agreement_path)})

    # -------------------------------------------------------------------------
    # Step 5: Record deal in SQLite
    # -------------------------------------------------------------------------
    # Schema: deals(deal_id, rfq_id, buyer_id, supplier_id, unit_price, quantity,
    #              total_amount, deal_hash, escrow_app_id, escrow_address, deadline,
    #              status, created_at, locked_at, delivered_at, completed_at)
    deadline_iso = datetime.fromtimestamp(deadline_ts, tz=timezone.utc).isoformat()
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO deals
            (deal_id, rfq_id, buyer_id, supplier_id, unit_price, quantity,
             total_amount, deal_hash, escrow_app_id, escrow_address, deadline,
             status, created_at, locked_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            deal_id,
            rfq_id,
            buyer_agent_id,
            supplier_id,
            unit_price,
            quantity,
            total_price,
            deal_hash,
            str(app_id),
            escrow_address,
            deadline_iso,
            status,
            now,
            now,   # locked_at
        ),
    )
    conn.commit()
    conn.close()
    logger.info("Deal recorded in database", extra={"deal_id": deal_id, "status": status})

    return SignResult(
        deal_id=deal_id,
        rfq_id=rfq_id,
        supplier_id=supplier_id,
        item=item,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        delivery_days=delivery_days,
        warranty_yrs=warranty_yrs,
        deal_hash=deal_hash,
        escrow_address=escrow_address,
        app_id=app_id,
        txid=txid,
        confirmed_round=confirmed_round,
        status=status,
    )
