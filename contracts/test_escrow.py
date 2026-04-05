"""
End-to-end escrow contract test: lock -> deliver -> release -> refund.

Usage: python contracts/test_escrow.py [--app-id N] [--network testnet]
"""
from __future__ import annotations

import argparse, json, os, time
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from algosdk.v2client.algod import AlgodClient
from algosdk.logic import get_application_address
from algosdk.transaction import (
    PaymentTxn, ApplicationCallTxn, StateSchema,
    assign_group_id, wait_for_confirmation,
)
from algosdk import mnemonic as mn
from algosdk.account import address_from_private_key, generate_account

from contracts.interact import get_escrow_state

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ALGOD_ADDRESS = os.getenv("ALGOD_ADDRESS", "https://testnet-api.algonode.cloud")
ALGOD_TOKEN   = os.getenv("ALGORAND_TOKEN", "")
CREATOR_MNEM  = os.getenv("ALGORAND_CREATOR_MNEMONIC", "")

CONFIG_FILE = Path(__file__).parent / "deploy_config.json"


def get_app_id(args) -> int:
    if args.app_id:
        return args.app_id
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())["app_id"]
    raise SystemExit("No app ID found. Run deploy.py first or pass --app-id.")


def get_buyer() -> tuple[bytes, str]:
    sk = mn.to_private_key(CREATOR_MNEM)
    return sk, address_from_private_key(sk)


def fresh_account() -> tuple[bytes, str]:
    sk, addr = generate_account()
    return sk, addr


def get_client() -> AlgodClient:
    return AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS)


def fund_account(client: AlgodClient, from_sk: bytes, from_addr: str, to_addr: str, microalgo: int) -> None:
    sp = client.suggested_params()
    txn = PaymentTxn(sender=from_addr, sp=sp, receiver=to_addr, amt=microalgo)
    client.send_transaction(txn.sign(from_sk))
    wait_for_confirmation(client, txn.get_txid(), 30)


def test_lock_deliver_release(client: AlgodClient, app_id: int, buyer_sk: bytes, buyer_addr: str):
    """Test happy path: LOCK -> DELIVERED -> COMPLETED"""
    app_addr = get_application_address(app_id)
    seller_sk, seller_addr = fresh_account()

    print(f"\n--- Test: lock -> deliver -> release ---")
    print(f"  App:      {app_id}")
    print(f"  Buyer:   {buyer_addr}")
    print(f"  Seller:  {seller_addr}")

    # Fund seller so they can pay fees
    fund_account(client, buyer_sk, buyer_addr, seller_addr, 500_000)

    # Step 1: Lock
    print("\n[1] LOCK escrow")
    sp = client.suggested_params()
    pay = PaymentTxn(sender=buyer_addr, sp=sp, receiver=app_addr, amt=1_000_000)
    app_txn = ApplicationCallTxn(
        sender=buyer_addr, sp=sp, index=app_id, on_complete=0,
        app_args=[b"lock", seller_addr.encode(),
                  b"sha256:deal-terms-hash", int(time.time() + 3600).to_bytes(8, "big")],
        accounts=[seller_addr],
    )
    assign_group_id([pay, app_txn])
    txid = client.send_transactions([pay.sign(buyer_sk), app_txn.sign(buyer_sk)])
    wait_for_confirmation(client, txid, 30)
    state = get_escrow_state(client, app_id)
    print(f"    state={state.state_name} amount={state.amount} seller={state.seller[:20]}...")

    # Step 2: Deliver
    print("\n[2] DELIVER")
    sp2 = client.suggested_params()
    deliver = ApplicationCallTxn(
        sender=seller_addr, sp=sp2, index=app_id, on_complete=0,
        app_args=[b"deliver", b"sha256:delivery-proof-payload"],
    )
    txid2 = client.send_transaction(deliver.sign(seller_sk))
    wait_for_confirmation(client, txid2, 30)
    state = get_escrow_state(client, app_id)
    print(f"    state={state.state_name} proof={state.proof_hash[:30]}...")

    # Step 3: Release
    print("\n[3] RELEASE")
    sp3 = client.suggested_params()
    release = ApplicationCallTxn(
        sender=buyer_addr, sp=sp3, index=app_id, on_complete=0,
        app_args=[b"release"],
    )
    txid3 = client.send_transaction(release.sign(buyer_sk))
    wait_for_confirmation(client, txid3, 30)
    state = get_escrow_state(client, app_id)
    print(f"    state={state.state_name}")

    buyer_bal = client.account_info(buyer_addr)["amount"] / 1e6
    seller_bal = client.account_info(seller_addr)["amount"] / 1e6
    print(f"\n  Buyer balance:   {buyer_bal:.3f} ALGO")
    print(f"  Seller balance: {seller_bal:.3f} ALGO")
    assert state.state_name == "COMPLETED", f"Expected COMPLETED, got {state.state_name}"
    assert seller_bal > 0.9, f"Expected ~1 ALGO for seller, got {seller_bal}"
    print("\n  PASS: lock -> deliver -> release")


def test_refund(client: AlgodClient, app_id: int, buyer_sk: bytes, buyer_addr: str):
    """Test timeout refund: LOCK -> (deadline passes) -> REFUNDED"""
    app_addr = get_application_address(app_id)
    seller_sk, seller_addr = fresh_account()

    print(f"\n--- Test: lock -> wait -> refund ---")
    print(f"  App:      {app_id}")
    print(f"  Buyer:   {buyer_addr}")
    print(f"  Seller:  {seller_addr}")

    # Fund seller
    fund_account(client, buyer_sk, buyer_addr, seller_addr, 500_000)

    # Step 1: Lock with 0-second deadline (expires immediately)
    print("\n[1] LOCK escrow (0s deadline)")
    sp = client.suggested_params()
    pay = PaymentTxn(sender=buyer_addr, sp=sp, receiver=app_addr, amt=500_000)
    app_txn = ApplicationCallTxn(
        sender=buyer_addr, sp=sp, index=app_id, on_complete=0,
        app_args=[b"lock", seller_addr.encode(),
                  b"sha256:refund-test-deal", int(time.time() - 1).to_bytes(8, "big")],  # deadline in past
        accounts=[seller_addr],
    )
    assign_group_id([pay, app_txn])
    txid = client.send_transactions([pay.sign(buyer_sk), app_txn.sign(buyer_sk)])
    wait_for_confirmation(client, txid, 30)
    state = get_escrow_state(client, app_id)
    print(f"    state={state.state_name} deadline={state.deadline}")

    # Step 2: Refund (buyer, after deadline)
    print("\n[2] REFUND")
    sp2 = client.suggested_params()
    refund = ApplicationCallTxn(
        sender=buyer_addr, sp=sp2, index=app_id, on_complete=0,
        app_args=[b"refund"],
    )
    txid2 = client.send_transaction(refund.sign(buyer_sk))
    wait_for_confirmation(client, txid2, 30)
    state = get_escrow_state(client, app_id)
    print(f"    state={state.state_name}")

    buyer_bal = client.account_info(buyer_addr)["amount"] / 1e6
    print(f"\n  Buyer balance: {buyer_bal:.3f} ALGO")
    assert state.state_name == "REFUNDED", f"Expected REFUNDED, got {state.state_name}"
    print("\n  PASS: lock -> refund")


def main():
    parser = argparse.ArgumentParser(description="Test escrow contract")
    parser.add_argument("--app-id", type=int, default=None)
    parser.add_argument("--network", default="testnet")
    parser.add_argument("--skip-lock-deliver-release", action="store_true")
    parser.add_argument("--skip-refund", action="store_true")
    args = parser.parse_args()

    app_id = get_app_id(args)
    buyer_sk, buyer_addr = get_buyer()
    client = get_client()

    print(f"Testing escrow app {app_id} on {args.network}")
    print(f"Buyer: {buyer_addr}")

    # Check current state
    try:
        state = get_escrow_state(client, app_id)
        print(f"Current state: {state.state_name}")
    except Exception as e:
        print(f"Could not read state: {e}")

    if not args.skip_lock_deliver_release:
        test_lock_deliver_release(client, app_id, buyer_sk, buyer_addr)

    if not args.skip_refund:
        test_refund(client, app_id, buyer_sk, buyer_addr)

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
