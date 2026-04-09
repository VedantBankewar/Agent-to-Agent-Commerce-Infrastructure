"""
Escrow contract interaction helpers.

Wraps algosdk v2client for the AgentTrade escrow contract.
All amounts in microALGO. Deadlines as Unix timestamps (seconds).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from algosdk.v2client.algod import AlgodClient
from algosdk.logic import get_application_address
from algosdk.transaction import (
    ApplicationCallTxn,
    PaymentTxn,
    StateSchema,
    wait_for_confirmation,
    assign_group_id,
)
from algosdk import encoding


# ---------------------------------------------------------------------------
# On-chain state values (must match escrow.py constants)
# ---------------------------------------------------------------------------

STATE_IDLE      = 0
STATE_LOCKED    = 1
STATE_DELIVERED = 2
STATE_COMPLETED = 3
STATE_REFUNDED  = 4

_STATE_NAMES = {
    STATE_IDLE:      "IDLE",
    STATE_LOCKED:    "LOCKED",
    STATE_DELIVERED: "DELIVERED",
    STATE_COMPLETED: "COMPLETED",
    STATE_REFUNDED:  "REFUNDED",
}

# Minimum balance requirement for escrow contract (microALGO)
MBR_MIN = 100_000


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EscrowState:
    state:      int
    state_name: str
    buyer:      str
    seller:     str
    amount:     int      # microALGO
    deal_hash:  str
    deadline:   int      # Unix timestamp
    proof_hash: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EscrowError(Exception):
    """Raised when a contract call fails."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_escrow_address(app_id: int) -> str:
    """Derive the Algorand address for an escrow app ID."""
    return get_application_address(app_id)


def state_name(state_val: int) -> str:
    return _STATE_NAMES.get(state_val, f"UNKNOWN({state_val})")


def wait_for_txn(client: AlgodClient, txid: str, timeout_secs: int = 30) -> dict:
    """Wait for a transaction to be confirmed, returning the confirmed round info."""
    try:
        return wait_for_confirmation(client, txid, timeout_secs)
    except Exception as e:
        raise EscrowError(f"Transaction {txid} not confirmed within {timeout_secs}s: {e}") from e


# ---------------------------------------------------------------------------
# Read-only queries
# ---------------------------------------------------------------------------

def get_escrow_state(client: AlgodClient, app_id: int) -> EscrowState:
    """
    Fetch and decode the current on-chain state of an escrow contract.

    Returns EscrowState with all fields. Missing/zero fields default to
    empty strings / 0.  Raises EscrowError if the app is not found.
    """
    app_info = client.application_info(app_id)
    if app_info is None:
        raise EscrowError(f"App {app_id} not found")

    raw_global = app_info.get("params", {}).get("global-state", [])

    # Build {key_str: value_dict} — key is decoded from base64 to an ASCII char
    state_map: dict = {}

    for kv in raw_global:
        key_b64 = kv["key"]            # e.g. "cw==" for key "s"
        value   = kv["value"]          # {"type": 0|1, "uint": ...|"bytes": ...}
        key_bytes = base64.b64decode(key_b64)
        try:
            key_str = key_bytes.decode("ascii")
        except Exception:
            key_str = key_bytes.hex()
        state_map[key_str] = value

    def get_bytes(key: str, default: str = "") -> str:
        raw = state_map.get(key)
        if raw is None:
            return default
        if raw.get("type") == 1:  # bytes
            b64 = raw.get("bytes", "")
            try:
                raw_bytes = base64.b64decode(b64)
                # Keys "b" and "u" are 32-byte raw public keys — convert to Algorand address
                if key in ("b", "u") and len(raw_bytes) == 32:
                    return encoding.encode_address(raw_bytes)
                return raw_bytes.decode("utf-8", errors="replace")
            except Exception:
                return b64
        return default

    def get_uint(key: str, default: int = 0) -> int:
        raw = state_map.get(key)
        if raw is None:
            return default
        return int(raw.get("uint", default))

    state_val  = get_uint("s")
    buyer      = get_bytes("b")
    seller     = get_bytes("u")
    amount     = get_uint("a")
    deal_hash  = get_bytes("h")
    deadline   = get_uint("d")
    proof_hash = get_bytes("p")

    return EscrowState(
        state      = state_val,
        state_name = state_name(state_val),
        buyer      = buyer,
        seller     = seller,
        amount     = amount,
        deal_hash  = deal_hash,
        deadline   = deadline,
        proof_hash = proof_hash,
    )


# ---------------------------------------------------------------------------
# Transaction builders — return signed transactions ready to broadcast
# ---------------------------------------------------------------------------

def build_lock_group_txn(
    client:           AlgodClient,
    buyer_address:    str,
    buyer_sk:         bytes,
    app_id:           int,
    seller_address:   str,
    deal_hash:        str,
    amount_microalgo:  int,
    deadline_ts:      int,
):
    """
    Build the 2-tx group for locking escrow:
      [0] Payment: buyer -> escrow contract address
      [1] AppCall: lock(deal_hash, deadline)

    The seller address is passed as Txn.accounts[1] (32-byte raw public key).
    Returns list of signed transactions.
    """
    escrow_addr = get_escrow_address(app_id)
    sp = client.suggested_params()

    pay_txn = PaymentTxn(
        sender            = buyer_address,
        sp                = sp,
        receiver          = escrow_addr,
        amt               = amount_microalgo,
        close_remainder_to = None,
    )

    app_txn = ApplicationCallTxn(
        sender      = buyer_address,
        sp          = sp,
        index       = app_id,
        on_complete = 0,   # NoOp
        app_args    = [
            b"lock",
            seller_address.encode("utf-8"),   # args[1]: seller address string
            deal_hash.encode("utf-8"),         # args[2]: deal hash
            deadline_ts.to_bytes(8, "big"),    # args[3]: deadline
        ],
        # seller as accounts[1] — contract reads Txn.accounts[1]
        accounts = [seller_address],
    )

    assign_group_id([pay_txn, app_txn])

    return [pay_txn.sign(buyer_sk), app_txn.sign(buyer_sk)]


def build_deliver_txn(
    client:          AlgodClient,
    supplier_address: str,
    supplier_sk:     bytes,
    app_id:          int,
    delivery_hash:   str,
):
    """Single AppCall for submit_delivery_proof."""
    sp = client.suggested_params()

    txn = ApplicationCallTxn(
        sender      = supplier_address,
        sp          = sp,
        index       = app_id,
        on_complete = 0,
        app_args    = [b"deliver", delivery_hash.encode("utf-8")],
    )
    return txn.sign(supplier_sk)


def build_release_txn(
    client:         AlgodClient,
    caller_address: str,
    caller_sk:      bytes,
    app_id:         int,
    seller_address: str = "",
):
    """Single AppCall for release_payment (permissionless after DELIVERED).

    The seller address must be passed in accounts[] so the AVM can resolve
    the inner-transaction receiver from global state.
    """
    sp = client.suggested_params()

    # If seller_address not provided, try to read it from on-chain state
    accounts = []
    if seller_address:
        accounts = [seller_address]
    else:
        try:
            state = get_escrow_state(client, app_id)
            if state.seller:
                accounts = [state.seller]
        except Exception:
            pass

    txn = ApplicationCallTxn(
        sender      = caller_address,
        sp          = sp,
        index       = app_id,
        on_complete = 0,
        app_args    = [b"release"],
        accounts    = accounts,
    )
    return txn.sign(caller_sk)


def build_refund_txn(
    client:        AlgodClient,
    buyer_address: str,
    buyer_sk:     bytes,
    app_id:        int,
):
    """Single AppCall for claim_refund (buyer only, after deadline).

    Buyer address is already the sender and is auto-available to the AVM,
    but we also add it to accounts[] for the inner-txn receiver resolution.
    """
    sp = client.suggested_params()

    txn = ApplicationCallTxn(
        sender      = buyer_address,
        sp          = sp,
        index       = app_id,
        on_complete = 0,
        app_args    = [b"refund"],
        accounts    = [buyer_address],
    )
    return txn.sign(buyer_sk)


# ---------------------------------------------------------------------------
# Send helpers — broadcast signed transactions and wait for confirmation
# ---------------------------------------------------------------------------

def lock_escrow(
    client:           AlgodClient,
    buyer_address:    str,
    buyer_sk:         bytes,
    app_id:           int,
    seller_address:   str,
    deal_hash:        str,
    amount_microalgo:  int,
    deadline_ts:      int,
) -> dict:
    """Full lock flow: build group, send atomically, wait for confirmation."""
    signed_txns = build_lock_group_txn(
        client, buyer_address, buyer_sk,
        app_id, seller_address, deal_hash, amount_microalgo, deadline_ts,
    )
    group_txid = client.send_transactions(signed_txns)
    result = wait_for_txn(client, group_txid)

    return {
        "txid":      group_txid,
        "confirmed": result.get("confirmed-round", 0),
        "app_id":    app_id,
        "escrow":    get_escrow_address(app_id),
        "amount":    amount_microalgo,
    }


def submit_delivery(
    client:          AlgodClient,
    supplier_address: str,
    supplier_sk:     bytes,
    app_id:          int,
    delivery_hash:   str,
) -> dict:
    """Submit delivery proof: sign + send + wait."""
    signed_txn = build_deliver_txn(
        client, supplier_address, supplier_sk, app_id, delivery_hash
    )
    txid = client.send_transaction(signed_txn)
    result = wait_for_txn(client, txid)

    return {
        "txid":      txid,
        "confirmed": result.get("confirmed-round", 0),
        "app_id":    app_id,
    }


def release_payment(
    client:         AlgodClient,
    caller_address: str,
    caller_sk:      bytes,
    app_id:         int,
    seller_address: str = "",
) -> dict:
    """Release payment to seller: sign + send + wait."""
    signed_txn = build_release_txn(client, caller_address, caller_sk, app_id, seller_address)
    txid = client.send_transaction(signed_txn)
    result = wait_for_txn(client, txid)

    return {
        "txid":      txid,
        "confirmed": result.get("confirmed-round", 0),
        "app_id":    app_id,
    }


def claim_refund(
    client:        AlgodClient,
    buyer_address: str,
    buyer_sk:      bytes,
    app_id:        int,
) -> dict:
    """Claim refund after deadline: sign + send + wait."""
    signed_txn = build_refund_txn(client, buyer_address, buyer_sk, app_id)
    txid = client.send_transaction(signed_txn)
    result = wait_for_txn(client, txid)

    return {
        "txid":      txid,
        "confirmed": result.get("confirmed-round", 0),
        "app_id":    app_id,
    }


# ---------------------------------------------------------------------------
# Config file helpers
# ---------------------------------------------------------------------------

CONFIG_FILE = "contracts/deploy_config.json"


def load_config() -> dict:
    """Load deployment config from deploy_config.json."""
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        raise EscrowError(f"{CONFIG_FILE} not found. Run deploy.py first.") from None


def save_config(app_id: int, app_address: str, network: str = "testnet") -> None:
    """Write app_id and address to deploy_config.json."""
    config = {"app_id": app_id, "address": app_address, "network": network}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
