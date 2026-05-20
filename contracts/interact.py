"""
Escrow contract interaction helpers.

Wraps algosdk v2client for the AgentTrade escrow contract.
All amounts in micro-USDC (6 decimals). Deadlines as Unix timestamps (seconds).
Settlement uses USDC (Algorand Standard Asset) instead of native ALGO.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from algosdk.v2client.algod import AlgodClient
from algosdk.logic import get_application_address
from algosdk.transaction import (
    ApplicationCallTxn,
    AssetTransferTxn,
    PaymentTxn,
    StateSchema,
    wait_for_confirmation,
    assign_group_id,
    OnComplete,
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

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EscrowState:
    state:      int
    state_name: str
    buyer:      str
    seller:     str
    amount:     int      # micro-USDC (6 decimals)
    deal_hash:  str
    deadline:   int      # Unix timestamp
    proof_hash: str
    token_id:   int = 0  # USDC ASA ID


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
    token_id   = get_uint("t")

    return EscrowState(
        state      = state_val,
        state_name = state_name(state_val),
        buyer      = buyer,
        seller     = seller,
        amount     = amount,
        deal_hash  = deal_hash,
        deadline   = deadline,
        proof_hash = proof_hash,
        token_id   = token_id,
    )


# ---------------------------------------------------------------------------
# Transaction builders — return signed transactions ready to broadcast
# ---------------------------------------------------------------------------

def build_optin_asset_txn(
    client:          AlgodClient,
    creator_address: str,
    creator_sk:      bytes,
    app_id:          int,
    asset_id:        int,
):
    """
    Build an AppCall to opt the escrow contract into a USDC ASA.

    Must be called by the contract creator before locking funds.
    The contract executes an inner AssetTransfer of 0 to itself.
    """
    sp = client.suggested_params()
    # Increase fee to cover inner txn
    sp.fee = 2000
    sp.flat_fee = True

    txn = ApplicationCallTxn(
        sender      = creator_address,
        sp          = sp,
        index       = app_id,
        on_complete = 0,  # NoOp
        app_args    = [b"optin_asset", asset_id.to_bytes(8, "big")],
        foreign_assets = [asset_id],
    )
    return txn.sign(creator_sk)


def build_lock_group_txn(
    client:           AlgodClient,
    buyer_address:    str,
    buyer_sk:         bytes,
    app_id:           int,
    seller_address:   str,
    deal_hash:        str,
    amount_micro_usdc: int,
    deadline_ts:      int,
    usdc_asset_id:    int,
):
    """
    Build the 2-tx group for locking escrow:
      [0] AssetTransfer (USDC): buyer -> escrow contract address
      [1] AppCall: lock(deal_hash, deadline)

    The seller address is passed as Txn.accounts[1] (32-byte raw public key).
    Returns list of signed transactions.
    """
    escrow_addr = get_escrow_address(app_id)
    sp = client.suggested_params()

    usdc_txn = AssetTransferTxn(
        sender   = buyer_address,
        sp       = sp,
        receiver = escrow_addr,
        amt      = amount_micro_usdc,
        index    = usdc_asset_id,
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
        foreign_assets = [usdc_asset_id],
    )

    assign_group_id([usdc_txn, app_txn])

    return [usdc_txn.sign(buyer_sk), app_txn.sign(buyer_sk)]


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
    The USDC ASA must be passed in foreign_assets[] for the inner ASA transfer.
    """
    sp = client.suggested_params()
    # Increase fee to cover inner txn
    sp.fee = 2000
    sp.flat_fee = True

    # Read on-chain state to get seller and USDC asset ID
    accounts = []
    foreign_assets = []
    try:
        state = get_escrow_state(client, app_id)
        if not seller_address and state.seller:
            seller_address = state.seller
        if state.token_id:
            foreign_assets = [state.token_id]
    except Exception:
        pass

    if seller_address:
        accounts = [seller_address]

    txn = ApplicationCallTxn(
        sender      = caller_address,
        sp          = sp,
        index       = app_id,
        on_complete = 0,
        app_args    = [b"release"],
        accounts    = accounts,
        foreign_assets = foreign_assets,
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
    The USDC ASA must be in foreign_assets[] for the inner ASA transfer.
    """
    sp = client.suggested_params()
    # Increase fee to cover inner txn
    sp.fee = 2000
    sp.flat_fee = True

    # Read on-chain state to get USDC asset ID
    foreign_assets = []
    try:
        state = get_escrow_state(client, app_id)
        if state.token_id:
            foreign_assets = [state.token_id]
    except Exception:
        pass

    txn = ApplicationCallTxn(
        sender      = buyer_address,
        sp          = sp,
        index       = app_id,
        on_complete = 0,
        app_args    = [b"refund"],
        accounts    = [buyer_address],
        foreign_assets = foreign_assets,
    )
    return txn.sign(buyer_sk)


# ---------------------------------------------------------------------------
# Send helpers — broadcast signed transactions and wait for confirmation
# ---------------------------------------------------------------------------

def optin_asset(
    client:          AlgodClient,
    creator_address: str,
    creator_sk:      bytes,
    app_id:          int,
    asset_id:        int,
) -> dict:
    """Opt the escrow contract into a USDC ASA."""
    signed_txn = build_optin_asset_txn(
        client, creator_address, creator_sk, app_id, asset_id,
    )
    txid = client.send_transaction(signed_txn)
    result = wait_for_txn(client, txid)

    return {
        "txid":      txid,
        "confirmed": result.get("confirmed-round", 0),
        "app_id":    app_id,
        "asset_id":  asset_id,
    }


def lock_escrow(
    client:           AlgodClient,
    buyer_address:    str,
    buyer_sk:         bytes,
    app_id:           int,
    seller_address:   str,
    deal_hash:        str,
    amount_micro_usdc: int,
    deadline_ts:      int,
    usdc_asset_id:    int = 0,
) -> dict:
    """Full lock flow: build group, send atomically, wait for confirmation.

    Uses USDC ASA transfer instead of native ALGO payment.
    """
    # Load USDC asset ID from config if not provided
    if not usdc_asset_id:
        config = load_config()
        usdc_asset_id = config.get("usdc_asset_id", 0)
        if not usdc_asset_id:
            raise EscrowError("USDC asset ID not configured. Run deploy.py first.")

    signed_txns = build_lock_group_txn(
        client, buyer_address, buyer_sk,
        app_id, seller_address, deal_hash,
        amount_micro_usdc, deadline_ts, usdc_asset_id,
    )
    group_txid = client.send_transactions(signed_txns)
    result = wait_for_txn(client, group_txid)

    return {
        "txid":      group_txid,
        "confirmed": result.get("confirmed-round", 0),
        "app_id":    app_id,
        "escrow":    get_escrow_address(app_id),
        "amount":    amount_micro_usdc,
        "usdc_asset_id": usdc_asset_id,
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


def delete_app(
    client:          AlgodClient,
    creator_address: str,
    creator_sk:      bytes,
    app_id:          int,
) -> dict:
    """Delete the application and reclaim its MBR back to the creator."""
    sp = client.suggested_params()

    txn = ApplicationCallTxn(
        sender      = creator_address,
        sp          = sp,
        index       = app_id,
        on_complete = OnComplete.DeleteApplicationOC,
        app_args    = [],
    )
    signed = txn.sign(creator_sk)
    txid = client.send_transaction(signed)
    result = wait_for_txn(client, txid)

    return {
        "txid":      txid,
        "confirmed": result.get("confirmed-round", 0),
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
