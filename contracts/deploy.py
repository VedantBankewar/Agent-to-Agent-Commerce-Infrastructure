"""
Deploy escrow contract to Algorand Testnet.

Usage:
    python -m contracts.deploy               # deploy to testnet
    python -m contracts.deploy --dry-run     # compile + validate only
    python -m contracts.deploy --reset       # delete existing app first
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

# Ensure the project root is on the path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from algosdk.v2client.algod import AlgodClient
from algosdk.logic import get_application_address
from algosdk.transaction import (
    ApplicationCallTxn,
    AssetConfigTxn,
    AssetTransferTxn,
    PaymentTxn,
    StateSchema,
    wait_for_confirmation,
    assign_group_id,
    OnComplete,
)
from algosdk import encoding

# Import escrow contract directly — compiles in-process
import contracts.escrow as escrow_module

# ---- Configuration ------------------------------------------------------------

TESTNET_ALGOD = "https://testnet-api.algonode.cloud"
MAINNET_ALGOD = "https://mainnet-api.algonode.cloud"

# Minimum balance requirement for the contract's global state + MBR (microALGO)
# Global: 7 bytes keys + 1 int key; base MBR 0.1 ALGO
MBR_FUNDING = 200_000   # 0.2 ALGO — covers global state MBR + a buffer

CONFIG_FILE = "contracts/deploy_config.json"


# ---- Helpers ------------------------------------------------------------------

def get_algod_client(network: str = "testnet") -> AlgodClient:
    """Build an AlgodClient from environment or default testnet."""
    if network == "testnet":
        url = os.environ.get("ALGORAND_TESTNET_URL", TESTNET_ALGOD)
        token = os.environ.get("ALGORAND_TOKEN", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    elif network == "mainnet":
        url = os.environ.get("ALGORAND_MAINNET_URL", MAINNET_ALGOD)
        token = os.environ.get("ALGORAND_TOKEN", "")
    else:
        raise ValueError(f"Unknown network: {network}")
    return AlgodClient(token, url)


def compile_contract() -> tuple[bytes, bytes]:
    """
    Compile the escrow contract using PyTeal.

    Returns (approval_teal, clear_teal) as bytes.
    """
    approval = escrow_module.compileTeal(
        escrow_module.approval_program(),
        mode=escrow_module.Mode.Application,
        version=8,
    )
    clear = escrow_module.compileTeal(
        escrow_module.clear_state_program(),
        mode=escrow_module.Mode.Application,
        version=8,
    )
    print(f"Compiled approval TEAL: {len(approval)} chars ({len(approval.encode())} bytes)")
    print(f"Compiled clear TEAL:    {len(clear)} chars ({len(clear.encode())} bytes)")
    return approval.encode(), clear.encode()


def compile_to_files(approval: bytes, clear: bytes) -> None:
    """Write compiled TEAL to .teal files."""
    root = Path(__file__).parent
    approval_path = root / "escrow_approval.teal"
    clear_path = root / "escrow_clear.teal"

    approval_path.write_bytes(approval)
    clear_path.write_bytes(clear)
    print(f"Wrote: {approval_path}")
    print(f"Wrote: {clear_path}")


def get_wallet_from_env() -> tuple[str, bytes]:
    """
    Load creator wallet address + private key from environment.

    Expects ALGORAND_CREATOR_ADDRESS and ALGORAND_CREATOR_MNEMONIC.
    Falls back to ALGORAND_ADDRESS + ALGORAND_MNEMONIC.
    """
    from algosdk import mnemonic

    address = (
        os.environ.get("ALGORAND_CREATOR_ADDRESS")
        or os.environ.get("ALGORAND_ADDRESS")
    )
    mnemonic_str = (
        os.environ.get("ALGORAND_CREATOR_MNEMONIC")
        or os.environ.get("ALGORAND_MNEMONIC")
    )

    if not address or not mnemonic_str:
        raise RuntimeError(
            "Missing wallet credentials. Set ALGORAND_CREATOR_ADDRESS and "
            "ALGORAND_CREATOR_MNEMONIC (or ALGORAND_ADDRESS + ALGORAND_MNEMONIC) "
            "in .env"
        )

    sk = mnemonic.to_private_key(mnemonic_str)
    return address, sk


def get_or_fund_deployer_wallet(client: AlgodClient, address: str, sk: bytes) -> tuple[str, bytes]:
    """
    Verify the deployer account exists on-chain. If it has 0 balance,
    fund it from the testnet faucet.

    Returns (address, sk).
    """
    account_info = client.account_info(address)
    balance = account_info.get("amount", 0)
    print(f"Deployer balance: {balance / 1e6:.3f} ALGO")

    if balance < MBR_FUNDING:
        faucet_addr = os.environ.get("ALGORAND_FAUCET_ADDRESS")
        faucet_sk = os.environ.get("ALGORAND_FAUCET_MNEMONIC")
        if not faucet_addr or not faucet_sk:
            raise RuntimeError(
                f"Deployer balance {balance / 1e6:.3f} ALGO is low. "
                "Set ALGORAND_FAUCET_ADDRESS and ALGORAND_FAUCET_MNEMONIC in .env to fund from faucet."
            )
        from algosdk import mnemonic
        faucet_sk_bytes = mnemonic.to_private_key(faucet_sk)

        # Fund deployer from faucet
        sp = client.suggested_params()
        pay_txn = PaymentTxn(
            sender    = faucet_addr,
            sp        = sp,
            receiver  = address,
            amt       = 2_000_000,  # 2 ALGO
            close_remainder_to = None,
        )
        signed = pay_txn.sign(faucet_sk_bytes)
        txid = client.send_transaction(signed)
        result = wait_for_confirmation(client, txid, 30)
        print(f"Funded deployer from faucet: txid={txid}, round={result.get('confirmed-round')}")

    return address, sk


# ---- Deploy ------------------------------------------------------------------

def deploy(
    client:         AlgodClient,
    creator_address: str,
    creator_sk:     bytes,
    global_schema:  StateSchema | None = None,
    local_schema:   StateSchema | None = None,
    dry_run:        bool = False,
) -> dict:
    """
    Compile + deploy the escrow contract.

    Returns dict with app_id, app_address, network.
    """
    # 1. Compile
    approval_teal, clear_teal = compile_contract()

    if dry_run:
        compile_to_files(approval_teal, clear_teal)
        print("[dry-run] Compiled successfully — no network calls made.")
        return {}

    # 2. Compile TEAL on-chain
    print("Compiling approval TEAL on-chain...")
    approval_result = client.compile(approval_teal.decode())
    approval_program = encoding.base64.b64decode(approval_result["result"])

    print("Compiling clear TEAL on-chain...")
    clear_result = client.compile(clear_teal.decode())
    clear_program = encoding.base64.b64decode(clear_result["result"])

    # 3. Create the application on-chain
    print("Creating application...")
    sp = client.suggested_params()

    app_txn = ApplicationCallTxn(
        sender       = creator_address,
        sp           = sp,
        index        = 0,
        on_complete  = 0,  # NoOp
        app_args     = [],
        approval_program = approval_program,
        clear_program    = clear_program,
        global_schema = global_schema if global_schema is not None else StateSchema(num_uints=4, num_byte_slices=7),
        local_schema  = local_schema  if local_schema  is not None else StateSchema(num_uints=0, num_byte_slices=0),
    )

    signed_app = app_txn.sign(creator_sk)
    txid = client.send_transaction(signed_app)
    result = wait_for_confirmation(client, txid, 30)
    confirmed_round = result.get("confirmed-round", 0)

    # Extract app ID from the app reference in the transaction result
    app_id = result.get("application-index")
    if not app_id:
        # Fallback: fetch from account info to find the new app
        # Since we know the creator and we just created the app, check pending
        raise RuntimeError(
            f"App creation transaction {txid} confirmed but app-id not in result. "
            f"Result: {result}"
        )

    print(f"Application created: app_id={app_id}")

    # 5. Derive app address and fund MBR
    app_address = get_application_address(app_id)
    creator_info = client.account_info(creator_address)
    app_account_info = client.account_info(app_address)
    app_balance = app_account_info.get("amount", 0)

    print(f"App account balance: {app_balance / 1e6:.3f} ALGO")

    # Fund app address with MBR if needed
    if app_balance < MBR_FUNDING:
        fund_amount = MBR_FUNDING - app_balance + 100_000  # extra for tx fee
        print(f"Funding app MBR: {fund_amount / 1e6:.3f} ALGO")
        sp2 = client.suggested_params()
        fund_txn = PaymentTxn(
            sender    = creator_address,
            sp        = sp2,
            receiver  = app_address,
            amt       = fund_amount,
            close_remainder_to = None,
        )
        signed_fund = fund_txn.sign(creator_sk)
        txid2 = client.send_transaction(signed_fund)
        wait_for_confirmation(client, txid2, 30)
        print(f"Funded app MBR: txid={txid2}")
    else:
        print("App account already has sufficient balance.")

    return {
        "app_id":       app_id,
        "address":      app_address,
        "txid":         txid,
        "confirmed":    confirmed_round,
    }


# ---- USDC ASA ----------------------------------------------------------------

def create_mock_usdc(
    client:          AlgodClient,
    creator_address: str,
    creator_sk:      bytes,
    total_supply:    int = 1_000_000_000_000,  # 1M USDC (6 decimals)
) -> int:
    """
    Create a mock USDC ASA on testnet for demo purposes.

    Returns the ASA ID.
    """
    sp = client.suggested_params()

    txn = AssetConfigTxn(
        sender         = creator_address,
        sp             = sp,
        total          = total_supply,
        default_frozen = False,
        unit_name      = "USDC",
        asset_name     = "Mock USDC (AgentTrade)",
        decimals       = 6,
        manager        = creator_address,
        reserve        = creator_address,
        strict_empty_address_check = False,
    )
    signed = txn.sign(creator_sk)
    txid = client.send_transaction(signed)
    result = wait_for_confirmation(client, txid, 30)

    asset_id = result.get("asset-index")
    if not asset_id:
        raise RuntimeError(f"ASA creation confirmed but asset-index not in result: {result}")

    print(f"Mock USDC ASA created: asset_id={asset_id}")
    return asset_id


def optin_and_fund_usdc(
    client:          AlgodClient,
    creator_address: str,
    creator_sk:      bytes,
    recipient_address: str,
    recipient_sk:    bytes,
    asset_id:        int,
    amount:          int,
) -> None:
    """
    Opt-in a recipient to the USDC ASA and transfer USDC to them.

    Args:
        amount: Amount in micro-USDC (6 decimals). E.g. 50_000_000_000 = $50,000 USDC.
    """
    sp = client.suggested_params()

    # Opt-in: recipient sends 0 of the ASA to themselves
    optin_txn = AssetTransferTxn(
        sender   = recipient_address,
        sp       = sp,
        receiver = recipient_address,
        amt      = 0,
        index    = asset_id,
    )
    signed_optin = optin_txn.sign(recipient_sk)
    txid = client.send_transaction(signed_optin)
    wait_for_confirmation(client, txid, 30)
    print(f"  Opted in {recipient_address[:8]}... to USDC ASA {asset_id}")

    # Transfer USDC from creator to recipient
    xfer_txn = AssetTransferTxn(
        sender   = creator_address,
        sp       = sp,
        receiver = recipient_address,
        amt      = amount,
        index    = asset_id,
    )
    signed_xfer = xfer_txn.sign(creator_sk)
    txid = client.send_transaction(signed_xfer)
    wait_for_confirmation(client, txid, 30)
    print(f"  Transferred {amount / 1_000_000:.2f} USDC to {recipient_address[:8]}...")


# ---- Reset -------------------------------------------------------------------

def reset(client: AlgodClient, creator_address: str, creator_sk: bytes) -> None:
    """Delete the existing escrow app."""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except FileNotFoundError:
        print("No deploy_config.json found, nothing to reset.")
        return

    app_id = config["app_id"]
    print(f"Deleting app {app_id}...")

    sp = client.suggested_params()
    txn = ApplicationCallTxn(
        sender      = creator_address,
        sp          = sp,
        index       = app_id,
        on_complete = OnComplete.DeleteApplicationOC,  # 5
        app_args    = [],
    )
    signed = txn.sign(creator_sk)
    txid = client.send_transaction(signed)
    wait_for_confirmation(client, txid, 30)
    print(f"Deleted app {app_id}: txid={txid}")

    Path(CONFIG_FILE).unlink(missing_ok=True)
    print("Removed deploy_config.json")


# ---- CLI --------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy AgentTrade escrow contract")
    parser.add_argument("--dry-run", action="store_true", help="Compile only, no network calls")
    parser.add_argument("--reset",  action="store_true", help="Delete existing app before deploying")
    parser.add_argument("--network", default="testnet", choices=["testnet", "mainnet"],
                        help="Network to deploy to (default: testnet)")
    args = parser.parse_args()

    network = args.network

    # Load config if exists
    config_path = Path(CONFIG_FILE)
    if config_path.exists():
        with open(config_path) as f:
            existing = json.load(f)
        print(f"Existing config: app_id={existing.get('app_id')}, "
              f"address={existing.get('address')}, network={existing.get('network')}")

    if args.reset:
        client = get_algod_client(network)
        address, sk = get_wallet_from_env()
        get_or_fund_deployer_wallet(client, address, sk)
        reset(client, address, sk)
        if not args.dry_run:
            print("Reset complete. Run again without --reset to redeploy.")

    if args.dry_run:
        print("[dry-run] Compiling contract only — no wallet or network calls needed.")
        approval_teal, clear_teal = compile_contract()
        compile_to_files(approval_teal, clear_teal)
        print("[dry-run] Done.")
        return

    client = get_algod_client(network)
    address, sk = get_wallet_from_env()

    # Ensure deployer is funded
    address, sk = get_or_fund_deployer_wallet(client, address, sk)

    print(f"\nDeploying to Algorand {network}")
    print(f"Deployer: {address}")
    print()

    result = deploy(
        client,
        creator_address = address,
        creator_sk      = sk,
        dry_run         = args.dry_run,
    )

    if result and not args.dry_run:
        app_id  = result["app_id"]
        app_addr = result["address"]

        # --- Create mock USDC ASA ---
        print("\n--- Creating Mock USDC ASA ---")
        usdc_asset_id_env = os.environ.get("USDC_ASSET_ID")
        if usdc_asset_id_env:
            usdc_asset_id = int(usdc_asset_id_env)
            print(f"Using existing USDC ASA from env: {usdc_asset_id}")
        else:
            usdc_asset_id = create_mock_usdc(client, address, sk)

        # --- Opt-in escrow contract to USDC ---
        print(f"\nOpting escrow contract into USDC ASA {usdc_asset_id}...")
        from contracts.interact import optin_asset
        optin_result = optin_asset(client, address, sk, app_id, usdc_asset_id)
        print(f"  Escrow opted in: txid={optin_result['txid']}")

        # Write config
        config = {
            "app_id":          app_id,
            "address":         app_addr,
            "network":         network,
            "usdc_asset_id":   usdc_asset_id,
            "confirmed_round": result.get("confirmed", 0),
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

        print(f"\nDeployed successfully!")
        print(f"  App ID:         {app_id}")
        print(f"  Address:        {app_addr}")
        print(f"  USDC ASA ID:    {usdc_asset_id}")
        print(f"  Config:        {CONFIG_FILE}")

        # Verify by reading state
        print("\nVerifying deployment...")
        from contracts import interact
        state = interact.get_escrow_state(client, app_id)
        print(f"  State:     {state.state_name} (expected: IDLE)")
        print(f"  Buyer:     {state.buyer or '(none)'}")
        print(f"  Seller:    {state.seller or '(none)'}")
        print(f"  Amount:    {state.amount} micro-USDC")
        print(f"  Token ID:  {state.token_id} (USDC ASA)")
        print(f"  Deal hash: {state.deal_hash or '(none)'}")
        print(f"  Deadline:  {state.deadline or '(none)'}")
        print(f"  Proof:     {state.proof_hash or '(none)'}")


if __name__ == "__main__":
    main()
