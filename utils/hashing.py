"""
SHA-256 hashing utilities for the Hash Bridge Pattern.
Full agreement data lives off-chain; only its fingerprint is anchored on-chain.
"""

from __future__ import annotations

import hashlib
import hmac
import json


def anchor_agreement(agreement: dict) -> str:
    """
    Compute the canonical SHA-256 fingerprint of an agreement dict.

    Canonical form: JSON with sorted keys (deterministic across runs and Python versions).
    Anchored on Algorand as: "sha256:<hex_digest>"
    """
    canonical = json.dumps(agreement, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def anchor_delivery_proof(delivery_proof: dict) -> str:
    """
    Compute SHA-256 fingerprint of a delivery proof dict.
    Mirrors anchor_agreement for consistency.
    """
    canonical = json.dumps(delivery_proof, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def verify_agreement(agreement: dict, on_chain_hash: str) -> bool:
    """
    Verify that an agreement dict matches a previously anchored hash.

    Returns True if the on-chain hash matches the computed fingerprint,
    indicating the agreement has not been tampered with.
    """
    expected = anchor_agreement(agreement)
    return hmac_safe_compare(expected, on_chain_hash)


def verify_delivery_proof(delivery_proof: dict, on_chain_hash: str) -> bool:
    """Verify a delivery proof against its anchored hash."""
    expected = anchor_delivery_proof(delivery_proof)
    return hmac_safe_compare(expected, on_chain_hash)


def hmac_safe_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.
    Uses hashlib.compare_digest where available (Python 3.3+).
    """
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
