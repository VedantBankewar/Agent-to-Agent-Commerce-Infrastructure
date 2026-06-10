"""One-command x402 end-to-end smoke test.

Runs the buyer side of the x402 flow against a running facilitator + supplier
server, with pre-flight checks that catch the common failure causes (facilitator
down, buyer not opted into USDC, buyer out of USDC) and report them clearly
instead of surfacing a raw SDK stack trace.

Prerequisites (see x402/README.md):
  1. Facilitator running:   uvicorn x402.facilitator_service:app --port 4000
  2. Supplier server running: uvicorn agents.supplier.x402_server:app --port 4100
  3. Buyer wallet (keys/<buyer-agent-id>.json) opted into the USDC ASA + funded.

Usage:
  python x402/smoke_test.py --buyer <buyer-agent-id>
  python x402/smoke_test.py --buyer demo-buyer --supplier-url http://localhost:4100/fulfill
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

# Ensure project root is importable when run as `python x402/smoke_test.py`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from x402.config import (  # noqa: E402
    ALGOD_SERVER,
    ALGOD_TOKEN,
    ALGORAND_TESTNET_CAIP2,
    FACILITATOR_URL,
    usdc_asset_id,
)

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}[WARN]{RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}[FAIL]{RESET} {msg}")


def check_facilitator(base_url: str) -> bool:
    """GET /health and /supported on the facilitator."""
    base = base_url.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=10) as r:
            health = json.loads(r.read())
        _ok(f"Facilitator /health: {health.get('status')} ({base})")
    except Exception as e:
        _fail(f"Facilitator unreachable at {base}: {e}")
        return False
    try:
        with urllib.request.urlopen(f"{base}/supported", timeout=10) as r:
            supported = json.loads(r.read())
        has_testnet = ALGORAND_TESTNET_CAIP2 in json.dumps(supported)
        if has_testnet:
            _ok("Facilitator /supported lists Algorand testnet")
        else:
            _warn(f"/supported did not list testnet CAIP-2: {supported}")
        return True
    except Exception as e:
        _fail(f"Facilitator /supported failed: {e}")
        return False


def check_buyer_usdc(buyer_agent_id: str, asa_id: int) -> bool:
    """Confirm the buyer wallet is opted into the USDC ASA and holds a balance."""
    try:
        from algosdk.v2client import algod
        from utils.wallet import load_wallet
    except Exception as e:
        _warn(f"Skipping buyer USDC check (import failed): {e}")
        return True

    try:
        wallet = load_wallet(buyer_agent_id)
    except Exception as e:
        _fail(f"Could not load buyer wallet '{buyer_agent_id}' from keys/: {e}")
        return False

    try:
        client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_SERVER)
        info = client.account_info(wallet.address)
    except Exception as e:
        _warn(f"Could not query algod for buyer balance: {e}")
        return True  # don't block the actual attempt

    algo = info.get("amount", 0) / 1e6
    if algo < 0.2:
        _warn(f"Buyer {wallet.address[:8]}... has {algo:.3f} ALGO — may be low for fees")
    opted = next((a for a in info.get("assets", []) if a.get("asset-id") == asa_id), None)
    if opted is None:
        _fail(f"Buyer is NOT opted into USDC ASA {asa_id}. Opt in + fund before paying.")
        return False
    bal = opted.get("amount", 0) / 1e6
    if bal <= 0:
        _fail(f"Buyer opted into ASA {asa_id} but holds 0 USDC. Fund the buyer.")
        return False
    _ok(f"Buyer {wallet.address[:8]}... holds {bal:,.2f} USDC (ASA {asa_id})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="x402 end-to-end smoke test (buyer side)")
    parser.add_argument("--buyer", default=os.getenv("X402_TEST_BUYER", "demo-buyer-agent"),
                        help="Buyer agent id (keys/<id>.json)")
    parser.add_argument("--supplier-url", default="http://localhost:4100/fulfill",
                        help="Supplier x402 /fulfill endpoint")
    parser.add_argument("--facilitator", default=FACILITATOR_URL, help="Facilitator base URL")
    parser.add_argument("--no-checks", action="store_true", help="Skip pre-flight checks")
    args = parser.parse_args()

    asa = usdc_asset_id()
    print(f"\n{DIM}USDC ASA: {asa} | network: {ALGORAND_TESTNET_CAIP2}{RESET}")
    print(f"{DIM}Facilitator: {args.facilitator} | Supplier: {args.supplier_url}{RESET}\n")

    if not args.no_checks:
        print("Pre-flight checks:")
        fac_ok = check_facilitator(args.facilitator)
        buyer_ok = check_buyer_usdc(args.buyer, asa)
        if not (fac_ok and buyer_ok):
            _fail("Pre-flight failed — fix the above before paying. (Use --no-checks to force.)")
            return 1
        print()

    print("Settling via x402...")
    try:
        from tools.x402_settle import settle_via_x402
    except Exception as e:
        _fail(f"Could not import x402 settle tool (is x402-avm installed?): {e}")
        return 1

    try:
        result = settle_via_x402(args.supplier_url, args.buyer)
    except Exception as e:
        _fail(f"Settlement raised: {type(e).__name__}: {e}")
        return 1

    print(json.dumps(result, indent=2, default=str))
    if result.get("status_code") == 200 and result.get("ok"):
        txid = result.get("txid")
        _ok(f"x402 settlement succeeded. txid: {txid or '(no header parsed)'}")
        if txid:
            print(f"  {DIM}https://lora.algokit.io/testnet/transaction/{txid}{RESET}")
        return 0
    _fail(f"Settlement did not succeed (status {result.get('status_code')}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
