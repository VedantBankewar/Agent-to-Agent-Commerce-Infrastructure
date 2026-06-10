"""Supplier-side x402 resource server.

Exposes a payment-gated ``POST /fulfill`` endpoint priced at the negotiated
deal total in USDC. The buyer agent (x402 client) calls it to settle a won
deal: the middleware returns ``402 Payment Required``, the client pays USDC via
the facilitator, and on success the supplier returns a fulfillment receipt.

Pricing is per-deal: the amount is fixed when the app is built (we know the
agreed total at settlement time), so we use the well-documented static-route
middleware with an explicit ``AssetAmount`` rather than guessing at per-request
dynamic pricing.

Run standalone for one deal (after a negotiation produces an amount):

    SUPPLIER_PAY_TO="<supplier algo address>" \
    X402_FULFILL_MICRO_USDC="100000000" \
    X402_USDC_ASSET_ID="10458941" \
    X402_FACILITATOR_URL="http://localhost:4000" \
      uvicorn agents.supplier.x402_server:app --port 4100

IMPORT-ROOT NOTE: tries `x402` first, falls back to `x402_avm` (see x402/README).
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request

# --- x402 SDK import (root ambiguity handled defensively) -------------------
try:
    from x402.server import x402ResourceServer  # type: ignore
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption  # type: ignore
    from x402.http.types import RouteConfig  # type: ignore
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI  # type: ignore
    from x402.mechanisms.avm.exact import ExactAvmServerScheme  # type: ignore
    from x402.schemas import AssetAmount  # type: ignore
except ImportError:  # some builds expose the root as `x402_avm`
    from x402_avm.server import x402ResourceServer  # type: ignore
    from x402_avm.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption  # type: ignore
    from x402_avm.http.types import RouteConfig  # type: ignore
    from x402_avm.http.middleware.fastapi import PaymentMiddlewareASGI  # type: ignore
    from x402_avm.mechanisms.avm.exact import ExactAvmServerScheme  # type: ignore
    from x402_avm.schemas import AssetAmount  # type: ignore

from x402.config import ALGORAND_TESTNET_CAIP2, FACILITATOR_URL, usdc_asset_id


def build_supplier_x402_app(
    pay_to: str,
    amount_micro_usdc: int,
    usdc_asa_id: int | None = None,
    *,
    facilitator_url: str | None = None,
    deal_id: str | None = None,
    item: str | None = None,
) -> FastAPI:
    """Build a FastAPI app with a payment-gated ``POST /fulfill`` for one deal.

    Args:
        pay_to: Supplier's Algorand address that receives the USDC.
        amount_micro_usdc: Negotiated deal total in micro-USDC (6 decimals).
        usdc_asa_id: USDC ASA id; defaults to the project config value.
        facilitator_url: Facilitator base URL; defaults to project config.
        deal_id / item: Optional metadata echoed back in the receipt.

    Returns:
        A configured FastAPI application.
    """
    asset_id = usdc_asa_id or usdc_asset_id()
    fac_url = facilitator_url or FACILITATOR_URL

    app = FastAPI(title="AgentTrade supplier x402 server")

    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=fac_url))
    server = x402ResourceServer(facilitator)
    server.register(ALGORAND_TESTNET_CAIP2, ExactAvmServerScheme())

    routes = {
        "POST /fulfill": RouteConfig(
            accepts=PaymentOption(
                scheme="exact",
                network=ALGORAND_TESTNET_CAIP2,
                pay_to=pay_to,
                price=AssetAmount(
                    amount=str(int(amount_micro_usdc)),
                    asset=str(asset_id),
                    extra={"name": "USDC", "decimals": 6},
                ),
            ),
            mime_type="application/json",
            description="Fulfil a negotiated procurement order (USDC settlement)",
        ),
    }

    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "service": "supplier-x402",
            "pay_to": pay_to,
            "amount_micro_usdc": int(amount_micro_usdc),
            "usdc_asa_id": asset_id,
        }

    @app.post("/fulfill")
    async def fulfill(request: Request):
        # Only reached after the middleware has verified + settled the payment.
        payment_payload = getattr(request.state, "payment_payload", None)
        paid_by = None
        if payment_payload is not None:
            try:
                paid_by = payment_payload.payload.get("from")
            except AttributeError:
                paid_by = None
        return {
            "fulfilled": True,
            "deal_id": deal_id,
            "item": item,
            "amount_micro_usdc": int(amount_micro_usdc),
            "paid_by": paid_by,
            "message": "Order confirmed. Settlement received via x402.",
        }

    return app


# Standalone launch: build the app from environment for a single deal.
app = build_supplier_x402_app(
    pay_to=os.getenv("SUPPLIER_PAY_TO", ""),
    amount_micro_usdc=int(os.getenv("X402_FULFILL_MICRO_USDC", "0") or 0),
    usdc_asa_id=int(os.getenv("X402_USDC_ASSET_ID", "0") or 0) or None,
    deal_id=os.getenv("X402_DEAL_ID"),
    item=os.getenv("X402_ITEM"),
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("X402_SUPPLIER_PORT", "4100")))
