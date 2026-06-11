"""Buyer-side x402 settlement tool.

The buyer agent uses this to settle a won deal by calling the winning
supplier's payment-gated ``/fulfill`` endpoint. The x402 client transparently:
  1. sends the request,
  2. receives ``402 Payment Required`` + PaymentRequirements,
  3. builds + signs the USDC payment group (via AlgorandClientSigner),
  4. retries with the payment, and
  5. returns the supplier's 200 fulfillment receipt.

Sync implementation (requests) to match the buyer agent's synchronous tools.

IMPORT-ROOT NOTE: tries `x402` first, falls back to `x402_avm` (see x402/README).
"""

from __future__ import annotations

from typing import Any

from x402pay.config import ALGORAND_TESTNET_CAIP2
from x402pay.signers import client_signer_from_agent
from utils.logger import get_logger

# --- x402 SDK import (root ambiguity handled defensively) -------------------
try:
    from x402 import x402ClientSync  # type: ignore
    from x402.http import x402HTTPClientSync  # type: ignore
    from x402.http.clients.requests import x402_requests  # type: ignore
    from x402.mechanisms.avm.exact.register import register_exact_avm_client  # type: ignore
except ImportError:  # some builds expose the root as `x402_avm`
    from x402_avm import x402ClientSync  # type: ignore
    from x402_avm.http import x402HTTPClientSync  # type: ignore
    from x402_avm.http.clients.requests import x402_requests  # type: ignore
    from x402_avm.mechanisms.avm.exact.register import register_exact_avm_client  # type: ignore

logger = get_logger("x402_settle")


def settle_via_x402(
    resource_url: str,
    buyer_agent_id: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Pay a supplier's x402-gated endpoint and return the settlement result.

    Args:
        resource_url: Full URL of the supplier's ``/fulfill`` endpoint.
        buyer_agent_id: Buyer agent id used to load the paying wallet.
        payload: Optional JSON body to POST with the order.
        timeout: Request timeout in seconds.

    Returns:
        Dict with status_code, ok, response body, and the settlement txid
        (if the supplier returned a payment-response header).
    """
    signer = client_signer_from_agent(buyer_agent_id)

    x402 = x402ClientSync()
    register_exact_avm_client(x402, signer, networks=ALGORAND_TESTNET_CAIP2)

    logger.info(
        "Settling via x402",
        extra={"resource_url": resource_url, "payer": signer.address},
    )

    result: dict[str, Any] = {"resource_url": resource_url, "payer": signer.address}

    with x402_requests(x402) as session:
        response = session.post(resource_url, json=payload or {}, timeout=timeout)
        result["status_code"] = response.status_code
        result["ok"] = bool(getattr(response, "ok", response.status_code < 400))
        try:
            result["response"] = response.json()
        except ValueError:
            result["response"] = response.text

        # Pull the on-chain settlement details from the response header, if present
        if result["ok"]:
            try:
                http_client = x402HTTPClientSync(x402)
                settle = http_client.get_payment_settle_response(
                    lambda name: response.headers.get(name)
                )
                settle_dict = (
                    settle.model_dump() if hasattr(settle, "model_dump") else dict(settle)
                )
                result["settlement"] = settle_dict
                result["txid"] = settle_dict.get("transaction") or settle_dict.get("txid")
            except (ValueError, AttributeError) as e:
                logger.warning("No settlement header parsed", extra={"error": str(e)})

    logger.info(
        "x402 settlement complete",
        extra={"status": result.get("status_code"), "txid": result.get("txid")},
    )
    return result
