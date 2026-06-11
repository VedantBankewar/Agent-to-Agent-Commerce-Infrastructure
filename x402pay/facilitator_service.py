"""x402 facilitator service for Algorand Testnet (AVM).

Verifies and settles x402 USDC payments on-chain on behalf of supplier
resource servers. Run it standalone:

    AVM_PRIVATE_KEY="<base64-64-byte-key>" \
      uvicorn x402.facilitator_service:app --port 4000

or, reusing the project deployer creds:

    ALGORAND_CREATOR_MNEMONIC="<25 words>" \
      uvicorn x402.facilitator_service:app --port 4000

Endpoints: GET /supported, POST /verify, POST /settle, GET /health.

IMPORT-ROOT NOTE: the x402-avm skill is inconsistent about whether the SDK is
imported as `x402` or `x402_avm`. We try `x402` first (per the detailed how-to
guides) and fall back to `x402_avm`. If neither matches your installed build,
adjust the import block below — the logic is otherwise unchanged.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Load project .env so ALGORAND_CREATOR_MNEMONIC / AVM_PRIVATE_KEY are available
# when this service is launched standalone via uvicorn.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from x402pay.signers import facilitator_signer_from_env

# --- x402 SDK import (root ambiguity handled defensively) -------------------
try:  # preferred: detailed-guide import root
    from x402 import x402Facilitator  # type: ignore
    from x402.mechanisms.avm.exact import register_exact_avm_facilitator  # type: ignore
    from x402.mechanisms.avm import ALGORAND_TESTNET_CAIP2  # type: ignore
except ImportError:  # some builds expose the root as `x402_avm`
    from x402_avm import x402Facilitator  # type: ignore
    from x402_avm.mechanisms.avm.exact import register_exact_avm_facilitator  # type: ignore
    from x402_avm.mechanisms.avm import ALGORAND_TESTNET_CAIP2  # type: ignore


app = FastAPI(title="AgentTrade x402 Facilitator (Algorand Testnet)")

_facilitator = None


def _get_facilitator():
    """Lazily build + cache the facilitator so the module imports without keys."""
    global _facilitator
    if _facilitator is None:
        signer = facilitator_signer_from_env()
        f = x402Facilitator()
        register_exact_avm_facilitator(f, signer, networks=[ALGORAND_TESTNET_CAIP2])
        _facilitator = f
    return _facilitator


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "x402-facilitator", "network": ALGORAND_TESTNET_CAIP2}


@app.get("/supported")
async def supported():
    return _get_facilitator().get_supported_networks()


@app.post("/verify")
async def verify(request: Request):
    body = await request.json()
    try:
        return await _get_facilitator().verify(
            body["paymentPayload"], body["paymentRequirements"]
        )
    except Exception as e:  # surface a clean 400 to the resource server
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.post("/settle")
async def settle(request: Request):
    body = await request.json()
    try:
        return await _get_facilitator().settle(
            body["paymentPayload"], body["paymentRequirements"]
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("x402.facilitator_service:app", host="0.0.0.0", port=4000, reload=False)
