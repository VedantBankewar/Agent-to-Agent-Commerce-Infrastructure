"""
Full Dry Run: RFQ -> Quotes -> Lock -> Deliver -> Release (Step 8.4)

Uses the creator wallet as buyer directly to avoid multi-fund issues.
"""
import sys, json, os, time, sqlite3, uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from utils.wallet import Wallet, save_wallet, get_algo_client
from utils.hashing import anchor_delivery_proof, anchor_agreement
from algosdk import mnemonic
from algosdk.account import address_from_private_key, generate_account
from algosdk.transaction import PaymentTxn, wait_for_confirmation
from contracts.interact import (
    get_escrow_state, lock_escrow, submit_delivery, release_payment, load_config
)

DB_PATH = str(ROOT / "db" / "hackathon.db")
client = get_algo_client()

# --- Creator wallet (used as buyer) ---
creator_mn = os.environ.get("ALGORAND_CREATOR_MNEMONIC", "").strip('"')
creator_sk = mnemonic.to_private_key(creator_mn)
creator_addr = address_from_private_key(creator_sk)

buyer_address = creator_addr
buyer_sk = creator_sk

buyer_bal = client.account_info(buyer_address)["amount"] / 1e6
print(f"Buyer (creator) balance: {buyer_bal:.3f} ALGO")

# =====================================================================
# Step 0: Verify contract is IDLE
# =====================================================================
config = load_config()
APP_ID = config["app_id"]
state = get_escrow_state(client, APP_ID)
print(f"Contract App {APP_ID} | State: {state.state_name}")
if state.state_name != "IDLE":
    print("ERROR: Contract is not IDLE.")
    sys.exit(1)

# =====================================================================
# Step 1: Create supplier wallet + fund for tx fees
# =====================================================================
print("\n[1] Creating supplier wallet...")
supplier_sk_raw, supplier_addr = generate_account()
supplier_mn = mnemonic.from_private_key(supplier_sk_raw)
supplier_wallet = Wallet(address=supplier_addr, private_key=supplier_sk_raw, mnemonic=supplier_mn)
save_wallet("dryrun-supplier", supplier_wallet)

# Fund supplier just enough for deliver tx fee
sp = client.suggested_params()
pay = PaymentTxn(sender=buyer_address, sp=sp, receiver=supplier_addr, amt=200_000)
txid = client.send_transaction(pay.sign(buyer_sk))
wait_for_confirmation(client, txid, 30)
print(f"  Supplier: {supplier_addr}")
print(f"  Funded: 0.2 ALGO")

# Register supplier in DB
SUPPLIER_ID = "dryrun-sup-" + uuid.uuid4().hex[:8]
conn = sqlite3.connect(DB_PATH)
now = datetime.now(timezone.utc).isoformat()
conn.execute(
    "INSERT INTO suppliers "
    "(supplier_id, name, category, wallet_addr, rating, min_price, base_cost, "
    "margin_pct, lead_days, warranty_yrs, created_at) "
    "VALUES (?, 'DryRunChairCo', 'furniture', ?, 4.5, 0.05, 0.08, 18.0, 7, 2.0, ?)",
    (SUPPLIER_ID, supplier_addr, now),
)

# Ensure buyer agent exists
conn.execute(
    "INSERT OR IGNORE INTO agents (agent_id, agent_type, name, wallet_addr, created_at) "
    "VALUES ('dryrun-buyer', 'procurement', 'DryRunBuyer', ?, ?)",
    (buyer_address, now),
)
conn.commit()

# =====================================================================
# Step 2: Create RFQ + Quote
# =====================================================================
print("\n[2] Creating RFQ and quote...")
rfq_id = str(uuid.uuid4())
valid_until = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

conn.execute(
    "INSERT INTO rfqs (rfq_id, agent_id, item, quantity, budget, deadline, category, status, created_at) "
    "VALUES (?, 'dryrun-buyer', 'ergonomic chairs', 5, 1, '2026-06-15', 'furniture', 'open', ?)",
    (rfq_id, now),
)

unit_price = 0.0944  # 0.08 * 1.18
total_price = round(unit_price * 5, 2)  # 0.47 ALGO
quote_id = str(uuid.uuid4())
conn.execute(
    "INSERT INTO quotes (quote_id, rfq_id, supplier_id, unit_price, total_price, "
    "delivery_days, warranty_yrs, valid_until, status, created_at) "
    "VALUES (?, ?, ?, ?, ?, 7, 2.0, ?, 'pending', ?)",
    (quote_id, rfq_id, SUPPLIER_ID, unit_price, total_price, valid_until, now),
)
conn.commit()
print(f"  RFQ: {rfq_id[:12]}...")
print(f"  Quote: ${unit_price:.4f}/unit, total=${total_price:.2f}")

# =====================================================================
# Step 3: Lock escrow
# =====================================================================
print("\n[3] Locking escrow on-chain...")
deadline_dt = datetime(2026, 6, 15, tzinfo=timezone.utc)
deadline_ts = int(deadline_dt.timestamp())

agreement = {
    "rfq_id": rfq_id, "supplier_id": SUPPLIER_ID, "item": "ergonomic chairs",
    "quantity": 5, "unit_price": unit_price, "total_price": total_price,
    "delivery_days": 7, "warranty_yrs": 2.0, "buyer_agent_id": "dryrun-buyer",
    "deadline": "2026-06-15",
}
deal_hash = anchor_agreement(agreement)
amount_microalgo = int(total_price * 1_000_000)
deal_id = str(uuid.uuid4())

lock_result = lock_escrow(
    client=client, buyer_address=buyer_address, buyer_sk=buyer_sk,
    app_id=APP_ID, seller_address=supplier_addr, deal_hash=deal_hash,
    amount_microalgo=amount_microalgo, deadline_ts=deadline_ts,
)
print(f"  Lock txid:   {lock_result['txid']}")
print(f"  Round:       {lock_result['confirmed']}")
state = get_escrow_state(client, APP_ID)
print(f"  State:       {state.state_name}")
assert state.state_name == "LOCKED"

# Record deal
conn.execute(
    "INSERT INTO deals (deal_id, rfq_id, buyer_id, supplier_id, unit_price, quantity, "
    "total_amount, deal_hash, escrow_app_id, escrow_address, deadline, status, created_at, locked_at) "
    "VALUES (?, ?, 'dryrun-buyer', ?, ?, 5, ?, ?, ?, ?, '2026-06-15', 'locked', ?, ?)",
    (deal_id, rfq_id, SUPPLIER_ID, unit_price, total_price, deal_hash,
     str(APP_ID), lock_result['escrow'], now, now),
)
conn.commit()

# =====================================================================
# Step 4: Submit delivery proof
# =====================================================================
print("\n[4] Submitting delivery proof on-chain...")
proof_data = {
    "deal_id": deal_id, "tracking_id": "TRACK-DRYRUN-001",
    "delivered_on": now, "items": "5 ergonomic chairs", "supplier_id": SUPPLIER_ID,
}
proof_hash = anchor_delivery_proof(proof_data)

deliver_result = submit_delivery(
    client=client, supplier_address=supplier_addr,
    supplier_sk=supplier_wallet.private_key, app_id=APP_ID, delivery_hash=proof_hash,
)
print(f"  Deliver txid: {deliver_result['txid']}")
print(f"  Round:        {deliver_result['confirmed']}")
state = get_escrow_state(client, APP_ID)
print(f"  State:        {state.state_name}")
assert state.state_name == "DELIVERED"

conn.execute("UPDATE deals SET status='delivered', delivered_at=? WHERE deal_id=?", (now, deal_id))
conn.commit()

# =====================================================================
# Step 5: Release payment
# =====================================================================
print("\n[5] Releasing payment on-chain...")
seller_before = client.account_info(supplier_addr)["amount"] / 1e6

release_result = release_payment(
    client=client, caller_address=buyer_address, caller_sk=buyer_sk,
    app_id=APP_ID, seller_address=supplier_addr,
)
print(f"  Release txid: {release_result['txid']}")
print(f"  Round:        {release_result['confirmed']}")
state = get_escrow_state(client, APP_ID)
print(f"  State:        {state.state_name}")
assert state.state_name == "COMPLETED"

seller_after = client.account_info(supplier_addr)["amount"] / 1e6
print(f"  Seller before: {seller_before:.3f} ALGO")
print(f"  Seller after:  {seller_after:.3f} ALGO")
print(f"  Received:      {seller_after - seller_before:.3f} ALGO")

conn.execute("UPDATE deals SET status='completed', completed_at=? WHERE deal_id=?", (now, deal_id))
conn.commit()
conn.close()

# =====================================================================
print("\n" + "=" * 60)
print("  FULL DRY RUN COMPLETE - ALL 5 STEPS PASSED")
print("=" * 60)
print(f"  App ID:        {APP_ID}")
print(f"  Deal ID:       {deal_id}")
print(f"  Lock txid:     {lock_result['txid']}")
print(f"  Deliver txid:  {deliver_result['txid']}")
print(f"  Release txid:  {release_result['txid']}")
print(f"  Final state:   {state.state_name}")
print(f"  Deal hash:     {deal_hash}")
print(f"  Proof hash:    {proof_hash}")
print(f"  Seller +ALGO:  {seller_after - seller_before:.3f}")
print("=" * 60)
