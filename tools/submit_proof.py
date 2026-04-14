"""
submit_proof — Supplier agent tool.
Read the delivery proof JSON, hash it, call submit_delivery() on-chain,
and record the proof hash in the deals table.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from utils.hashing import anchor_delivery_proof
from utils.logger import get_logger, log_txn
from utils.wallet import get_algo_client


DATABASE_PATH    = os.getenv("DATABASE_PATH", "db/hackathon.db")
DELIVERY_DIR     = os.getenv("DELIVERY_DIR",  "delivery")
CONFIG_FILE      = "contracts/deploy_config.json"


def submit_proof(
    deal_id: str,
    delivery_proof: dict | None = None,
) -> dict:
    """
    Anchor a delivery proof on-chain and update the deal record.

    Workflow:
      1. Load or use provided delivery_proof dict from the delivery/ directory
      2. Compute sha256:hash via utils.hashing.anchor_delivery_proof()
      3. Call contracts/interact.submit_delivery() on Algorand
      4. Update deals table with proof_hash, set status to 'delivered'

    Args:
        deal_id:          The deal ID from the deals table.
        delivery_proof:   Optional pre-loaded proof dict.
                          If None, loads from delivery/{deal_id}.json.

    Returns:
        dict with proof_hash, txid, confirmed_round, and deal status.
    """
    logger = get_logger("submit_proof")

    db_path     = Path(DATABASE_PATH)
    config_path = Path(CONFIG_FILE)

    # 1. Load delivery proof
    if delivery_proof is None:
        proof_path = Path(DELIVERY_DIR) / f"{deal_id}.json"
        if not proof_path.exists():
            raise FileNotFoundError(
                f"Delivery proof not found: {proof_path}. "
                "Create delivery/{deal_id}.json first."
            )
        with open(proof_path) as f:
            delivery_proof = json.load(f)

    # 2. Hash the proof
    proof_hash = anchor_delivery_proof(delivery_proof)

    # 3. Load escrow config
    if not config_path.exists():
        raise FileNotFoundError(
            f"{config_path} not found. Deploy the escrow contract first."
        )
    with open(config_path) as f:
        config = json.load(f)
    app_id = config["app_id"]

    # 4. Look up deal and supplier details from SQLite
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT d.deal_id, d.supplier_id, d.rfq_id, d.status,
               s.wallet_addr
        FROM deals d
        JOIN suppliers s ON s.supplier_id = d.supplier_id
        WHERE d.deal_id = ?
        """,
        (deal_id,),
    )
    deal_row = cursor.fetchone()
    conn.close()

    if deal_row is None:
        raise ValueError(f"Deal {deal_id} not found in database.")

    if deal_row["status"] == "delivered":
        return {
            "deal_id":    deal_id,
            "proof_hash": proof_hash,
            "txid":       None,
            "confirmed":  None,
            "status":     "already delivered",
        }

    if deal_row["status"] not in ("locked"):
        raise ValueError(
            f"Deal {deal_id} is {deal_row['status']}, expected 'locked' before submitting proof."
        )

    # 5. Load supplier wallet via wallet.py get_supplier_wallet
    from utils.wallet import get_supplier_wallet

    wallet = get_supplier_wallet(deal_row["supplier_id"])
    if wallet is None:
        raise ValueError(
            f"Supplier wallet not found for {deal_row['supplier_id']}. "
            "Ensure keys/{supplier_id}.json exists."
        )

    client = get_algo_client()

    # 6. Call on-chain submit_delivery via interact.py
    from contracts.interact import submit_delivery

    result = submit_delivery(
        client=client,
        supplier_address=wallet.address,
        supplier_sk=wallet.private_key,
        app_id=app_id,
        delivery_hash=proof_hash,
    )

    log_txn(logger, result["txid"], deal_id=deal_id, proof_hash=proof_hash, confirmed=result["confirmed"])

    # 7. Update deals table
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE deals
        SET status       = 'delivered',
            delivered_at = ?
        WHERE deal_id = ?
        """,
        (now, deal_id),
    )
    conn.commit()
    conn.close()

    return {
        "deal_id":    deal_id,
        "proof_hash": proof_hash,
        "txid":       result["txid"],
        "confirmed":  result["confirmed"],
        "status":     "delivered",
    }
