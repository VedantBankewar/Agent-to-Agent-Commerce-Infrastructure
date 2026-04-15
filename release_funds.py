import sqlite3
import json
import os
from datetime import datetime, timezone
import time
from pathlib import Path

from tools.submit_proof import submit_proof
from contracts.interact import release_payment, load_config
from utils.wallet import get_algo_client, load_wallet
from utils.logger import get_logger, log_txn

DATABASE_PATH = "db/hackathon.db"
DELIVERY_DIR = "delivery"

def log_color(msg):
    print(f"\033[36m{msg}\033[0m")

def release_funds():
    logger = get_logger("release_funds")
    db_path = Path(DATABASE_PATH)
    
    # 1. Locate Locked Deal
    print("\n[1] Finding locked deal...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT deal_id, supplier_id, buyer_id FROM deals WHERE status = 'locked' AND supplier_id NOT LIKE 'dryrun%' ORDER BY locked_at DESC LIMIT 1")
    deal = cursor.fetchone()
    
    if not deal:
        print("No locked deals found! Exiting.")
        return
        
    deal_id = deal["deal_id"]
    buyer_id = deal["buyer_id"]
    supplier_id = deal["supplier_id"]
    print(f"    Found deal_id: {deal_id}")
    
    # 2. Generate Mock Delivery Proof
    print("\n[2] Generating mock delivery proof...")
    Path(DELIVERY_DIR).mkdir(exist_ok=True)
    proof_path = Path(DELIVERY_DIR) / f"{deal_id}.json"
    proof_payload = {
        "tracking_number": "AWS-FEDEX-" + str(int(time.time())),
        "carrier": "FedEx",
        "delivered_on": datetime.now(timezone.utc).isoformat(),
        "status": "delivered_to_destination"
    }
    with open(proof_path, "w") as f:
        json.dump(proof_payload, f, indent=2)
    print(f"    Saved delivery proof to {proof_path}")

    # 2.5 Fund the supplier with 0.15 ALGO so they can pay transaction fees
    print("\n[2.5] Funding supplier wallet from deployer...")
    try:
        from utils.wallet import load_wallet, sign_and_send_txn
        deployer = load_wallet("deployer")
        supplier_wallet = load_wallet(supplier_id)
        sign_and_send_txn(deployer, supplier_wallet.address, 150000, note="Supplier release funding")
        print("    Supplier wallet funded for transactions.")
    except Exception as e:
        print(f"    Failed to fund supplier: {e}")

    # 3. Submit Delivery Proof On-Chain
    print("\n[3] Submitting delivery proof on-chain (contract -> DELIVERED)...")
    res = submit_proof(deal_id, delivery_proof=proof_payload)
    print(f"    txid: {res['txid']}")
    print(f"    proof_hash: {res['proof_hash']}")
    
    # 4. Release Payment On-Chain
    print("\n[4] Releasing payment on-chain (contract -> COMPLETED)...")
    config = load_config()
    app_id = config["app_id"]
    client = get_algo_client()
    
    # We use buyer wallet or anyone's wallet, here we use buyer for simplicity as they must exist
    # wait, could there be no key? Let's get the buyer wallet.
    buyer_wallet = load_wallet(buyer_id)
    if not buyer_wallet:
        raise ValueError(f"Could not load buyer wallet for {buyer_id}")
        
    release_res = release_payment(
        client=client,
        caller_address=buyer_wallet.address,
        caller_sk=buyer_wallet.private_key,
        app_id=app_id
    )
    print(f"    Payment released! txid: {release_res['txid']}")
    
    # 5. Update SQLite Database
    cursor.execute("UPDATE deals SET status = 'completed' WHERE deal_id = ?", (deal_id,))
    conn.commit()
    conn.close()
    
    print(f"\n[5] Database updated. Deal {deal_id} is COMPLETED.\n")

    # 6. Cleanup (Reclaim MBR)
    print("\n[6] Reclaiming MBR funds (deleting app)...")
    try:
        from contracts.interact import delete_app
        deployer = load_wallet("deployer")
        del_res = delete_app(
            client=client,
            creator_address=deployer.address,
            creator_sk=deployer.private_key,
            app_id=app_id
        )
        print(f"    App {app_id} deleted. MBR reclaimed! txid: {del_res['txid']}")
    except Exception as e:
        print(f"    Failed to reclaim MBR: {e}")

    log_color("Successfully released escrow funds to the supplier!")

if __name__ == "__main__":
    release_funds()
