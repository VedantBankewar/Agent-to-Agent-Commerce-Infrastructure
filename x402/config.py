"""Shared configuration for the x402 payment layer.

Pure stdlib + filesystem — no x402 SDK import, so this module is always
importable and unit-testable regardless of whether x402-avm is installed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# CAIP-2 network identifier for Algorand Testnet (genesis hash of testnet-v1.0).
# Matches the value the x402-avm SDK exposes as ALGORAND_TESTNET_CAIP2; we keep
# a literal here so config has zero SDK dependency, but prefer the SDK constant
# in code that already imports the SDK.
ALGORAND_TESTNET_CAIP2 = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="

# URL of the facilitator that verifies + settles AVM payments.
FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "http://localhost:4000")

# Algod endpoint used by the facilitator signer.
ALGOD_SERVER = os.getenv("ALGOD_SERVER", os.getenv("ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"))
ALGOD_TOKEN = os.getenv("ALGOD_TOKEN", os.getenv("ALGORAND_TOKEN", ""))


def usdc_asset_id() -> int:
    """Resolve the USDC ASA id used for x402 settlement.

    Priority: X402_USDC_ASSET_ID env → contracts/deploy_config.json → 0.

    NOTE: the escrow deploy currently mints a *fresh* mock USDC ASA per run
    (see [[agenttrade-funding-gotcha]]). For x402, prefer a stable ASA via
    X402_USDC_ASSET_ID so the buyer's opt-in/funding survives across runs.
    """
    env = os.getenv("X402_USDC_ASSET_ID")
    if env:
        return int(env)
    cfg = ROOT / "contracts" / "deploy_config.json"
    if cfg.exists():
        try:
            return int(json.loads(cfg.read_text()).get("usdc_asset_id") or 0)
        except (ValueError, OSError, json.JSONDecodeError):
            pass
    return 0
