"""
Algorand wallet creation and transaction signing utilities.

Each agent gets a Testnet wallet — address serves as on-chain DID.
Private keys are stored securely off-chain, never in source or logs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import algosdk
from algosdk import account, encoding, mnemonic
from algosdk.transaction import PaymentTxn, wait_for_confirmation
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Wallet:
    """Represents an agent's Algorand wallet."""

    address: str
    private_key: str
    mnemonic: str

    @classmethod
    def generate(cls) -> Wallet:
        """Generate a new Testnet wallet for an agent."""
        private_key, address = account.generate_account()
        mn = mnemonic.from_private_key(private_key)
        return cls(address=address, private_key=private_key, mnemonic=mn)

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "mnemonic": self.mnemonic,
        }


# ---------------------------------------------------------------------------
# Algorand client helpers
# ---------------------------------------------------------------------------


def get_algo_client() -> AlgodClient:
    """Return an AlgodClient connected to Algorand Testnet."""
    token = os.getenv("ALGORAND_TOKEN", "")
    return AlgodClient(token, "https://testnet-api.algonode.cloud")


def get_indexer_client() -> IndexerClient:
    """Return an IndexerClient connected to Algorand Testnet."""
    token = os.getenv("ALGORAND_TOKEN", "")
    return IndexerClient(token, "https://testnet-indexer.algonode.cloud")


# ---------------------------------------------------------------------------
# Wallet persistence
# ---------------------------------------------------------------------------

WALLET_DIR = Path(__file__).parent.parent / "keys"
WALLET_DIR.mkdir(exist_ok=True)


def save_wallet(agent_id: str, wallet: Wallet) -> Path:
    """Persist wallet to keys/ directory. Returns path to file."""
    path = WALLET_DIR / f"{agent_id}.json"
    import json

    with open(path, "w") as f:
        json.dump(wallet.to_dict(), f, indent=2)
    return path


def load_wallet(agent_id: str) -> Wallet:
    """Load a previously saved wallet."""
    import json

    path = WALLET_DIR / f"{agent_id}.json"
    with open(path) as f:
        data = json.load(f)
    return Wallet(
        address=data["address"],
        private_key=mnemonic.to_private_key(data["mnemonic"]),
        mnemonic=data["mnemonic"],
    )


def get_supplier_wallet(supplier_id: str) -> Wallet | None:
    """
    Load a supplier's wallet by supplier_id.
    Wallets are stored at keys/{supplier_id}.json.
    Returns None if the wallet file does not exist.
    """
    path = WALLET_DIR / f"{supplier_id}.json"
    if not path.exists():
        return None
    import json

    with open(path) as f:
        data = json.load(f)
    return Wallet(
        address=data["address"],
        private_key=mnemonic.to_private_key(data["mnemonic"]),
        mnemonic=data["mnemonic"],
    )


# ---------------------------------------------------------------------------
# Wallet operations
# ---------------------------------------------------------------------------


def validate_address(address: str) -> bool:
    """Validate Algorand address format."""
    try:
        encoding.decode_address(address)
        return len(address) == 58
    except Exception:
        return False


def get_balance(address: str) -> int:
    """Return balance in microALGO."""
    client = get_algo_client()
    account_info = client.account_info(address)
    return account_info.get("amount", 0)


def fund_wallet_from_faucet(address: str, microns: int = 5_000_000) -> str:
    """
    Request Testnet ALGO from the Algorand faucet.
    Default: 5 ALGO (5_000_000 microALGO).
    Returns transaction ID.
    """
    import requests

    faucet_url = "https://dispenser.testnet.algorand.org"
    payload = {"address": address, "amount": microns}
    resp = requests.post(faucet_url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("txId", "")


def sign_and_send_txn(
    wallet: Wallet,
    receiver: str,
    amount: int,
    note: str = "",
) -> dict:
    """
    Sign a payment transaction with the given wallet and broadcast it.
    Returns confirmed transaction info.

    Args:
        wallet: Signing wallet
        receiver: Recipient address
        amount: Amount in microALGO
        note: Optional note field (max 1KB)
    """
    client = get_algo_client()

    params = client.suggested_params()
    unsigned_txn = PaymentTxn(
        sender=wallet.address,
        sp=params,
        receiver=receiver,
        amt=amount,
        note=note.encode(),
    )

    signed_txn = unsigned_txn.sign(wallet.private_key)
    tx_id = client.send_transaction(signed_txn)
    result = wait_for_confirmation(client, tx_id, 10)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Algorand wallet utilities")
    parser.add_argument("--create", metavar="AGENT_ID", help="Generate and save a new wallet")
    parser.add_argument("--balance", metavar="ADDRESS", help="Check balance of an address")
    parser.add_argument("--fund", metavar="ADDRESS", help="Request faucet funds for an address")

    args = parser.parse_args()

    if args.create:
        wallet = Wallet.generate()
        path = save_wallet(args.create, wallet)
        print(f"Wallet created for {args.create}")
        print(f"  Address: {wallet.address}")
        print(f"  Saved to: {path}")

    elif args.balance:
        bal = get_balance(args.balance)
        print(f"Balance: {bal:,} microALGO ({bal / 1_000_000:.6f} ALGO)")

    elif args.fund:
        tx_id = fund_wallet_from_faucet(args.fund)
        print(f"Faucet request sent. Tx ID: {tx_id}")

    else:
        parser.print_help()
