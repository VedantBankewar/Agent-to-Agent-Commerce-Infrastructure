"""Algorand signers for the x402 payment layer.

Two signer implementations the x402-avm SDK expects:

  * AlgorandClientSigner    — used by the buyer agent (x402 client) to sign the
                              payment transaction group.
  * AlgorandFacilitatorSigner — used by the facilitator service to simulate,
                              sign, submit, and confirm the payment group on
                              Algorand.

Both follow the patterns in the algorand-x402-python skill. This module depends
only on `algosdk` (already a project dependency), NOT on the x402 SDK, so it is
fully importable and testable on its own.

algosdk key formats:
  - `Wallet.private_key` (utils/wallet.py) and `mnemonic.to_private_key(mn)`
    return a **base64-encoded 64-byte** key (32-byte seed + 32-byte pubkey),
    which is exactly what `Transaction.sign()` expects. We pass it straight
    through.
"""

from __future__ import annotations

import base64
import os

from algosdk import encoding, mnemonic, transaction
from algosdk.v2client import algod


# ---------------------------------------------------------------------------
# Client signer (buyer agent)
# ---------------------------------------------------------------------------

class AlgorandClientSigner:
    """ClientAvmSigner: signs the x402 payment txn group for the buyer.

    Args:
        private_key_b64: algosdk base64 private key (64-byte key, base64). This
            is exactly `utils.wallet.Wallet.private_key`.
    """

    def __init__(self, private_key_b64: str) -> None:
        self._sk_b64 = private_key_b64
        raw = base64.b64decode(private_key_b64)
        if len(raw) != 64:
            raise ValueError("private key must decode to 64 bytes")
        self._address = encoding.encode_address(raw[32:])

    @property
    def address(self) -> str:
        return self._address

    def sign_transactions(
        self,
        unsigned_txns: list[bytes],
        indexes_to_sign: list[int],
    ) -> list[bytes | None]:
        """Sign the transactions at `indexes_to_sign`, leaving others as None.

        algosdk encoding boundary: `msgpack_decode` expects a base64 string and
        `msgpack_encode` returns one, so we convert at the edges.
        """
        result: list[bytes | None] = []
        for i, txn_bytes in enumerate(unsigned_txns):
            if i in indexes_to_sign:
                txn = encoding.msgpack_decode(base64.b64encode(txn_bytes).decode())
                signed = txn.sign(self._sk_b64)
                result.append(base64.b64decode(encoding.msgpack_encode(signed)))
            else:
                result.append(None)
        return result


def client_signer_from_agent(agent_id: str) -> AlgorandClientSigner:
    """Build a client signer from a stored project wallet (keys/{agent_id}.json)."""
    from utils.wallet import load_wallet

    wallet = load_wallet(agent_id)
    return AlgorandClientSigner(wallet.private_key)


# ---------------------------------------------------------------------------
# Facilitator signer (settlement service)
# ---------------------------------------------------------------------------

class AlgorandFacilitatorSigner:
    """FacilitatorAvmSigner: simulate, sign, submit, and confirm payment groups.

    Args:
        private_key_b64: algosdk base64 private key (64-byte key, base64).
        algod_url: algod endpoint; defaults to testnet AlgoNode if empty.
        algod_token: algod token (usually empty for public nodes).
    """

    def __init__(self, private_key_b64: str, algod_url: str = "", algod_token: str = "") -> None:
        self._secret_key = base64.b64decode(private_key_b64)
        if len(self._secret_key) != 64:
            raise ValueError("private key must decode to 64 bytes")
        self._address = encoding.encode_address(self._secret_key[32:])
        self._signing_key = private_key_b64
        self._clients: dict[str, algod.AlgodClient] = {}
        self._default_client = algod.AlgodClient(algod_token, algod_url) if algod_url else None

    def _get_client(self, network: str) -> algod.AlgodClient:
        if network not in self._clients:
            if self._default_client:
                self._clients[network] = self._default_client
            else:
                self._clients[network] = algod.AlgodClient("", "https://testnet-api.algonode.cloud")
        return self._clients[network]

    def get_addresses(self) -> list[str]:
        return [self._address]

    def sign_transaction(self, txn_bytes: bytes, fee_payer: str, network: str) -> bytes:
        b64 = base64.b64encode(txn_bytes).decode("utf-8")
        txn_obj = encoding.msgpack_decode(b64)
        signed = txn_obj.sign(self._signing_key)
        return base64.b64decode(encoding.msgpack_encode(signed))

    def sign_group(self, group_bytes, fee_payer, indexes_to_sign, network):
        result = list(group_bytes)
        for i in indexes_to_sign:
            result[i] = self.sign_transaction(group_bytes[i], fee_payer, network)
        return result

    def simulate_group(self, group_bytes, network):
        client = self._get_client(network)
        stxns = []
        for txn_bytes in group_bytes:
            b64 = base64.b64encode(txn_bytes).decode("utf-8")
            obj = encoding.msgpack_decode(b64)
            if isinstance(obj, transaction.SignedTransaction):
                stxns.append(obj)
            else:
                stxns.append(transaction.SignedTransaction(obj, None))
        req = transaction.SimulateRequest(
            txn_groups=[transaction.SimulateRequestTransactionGroup(txns=stxns)],
            allow_empty_signatures=True,
        )
        result = client.simulate_raw_transactions(req)
        for group in result.get("txn-groups", []):
            if group.get("failure-message"):
                raise Exception(f"Simulation failed: {group['failure-message']}")

    def send_group(self, group_bytes, network):
        client = self._get_client(network)
        return client.send_raw_transaction(base64.b64encode(b"".join(group_bytes)))

    def confirm_transaction(self, txid, network, rounds=4):
        client = self._get_client(network)
        transaction.wait_for_confirmation(client, txid, rounds)


def _private_key_b64_from_env() -> str:
    """Resolve a base64 64-byte private key for the facilitator.

    Priority: AVM_PRIVATE_KEY (base64 64-byte) → ALGORAND_CREATOR_MNEMONIC
    (25-word mnemonic, converted) → error.
    """
    direct = os.getenv("AVM_PRIVATE_KEY")
    if direct:
        return direct
    mn = os.getenv("ALGORAND_CREATOR_MNEMONIC", "").strip('"')
    if mn:
        return mnemonic.to_private_key(mn)
    raise RuntimeError(
        "No facilitator key. Set AVM_PRIVATE_KEY (base64 64-byte) or "
        "ALGORAND_CREATOR_MNEMONIC in the environment."
    )


def facilitator_signer_from_env() -> AlgorandFacilitatorSigner:
    """Build the facilitator signer from environment configuration."""
    from x402pay.config import ALGOD_SERVER, ALGOD_TOKEN

    return AlgorandFacilitatorSigner(
        private_key_b64=_private_key_b64_from_env(),
        algod_url=ALGOD_SERVER,
        algod_token=ALGOD_TOKEN,
    )
