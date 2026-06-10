# x402 payment layer — install & testnet runbook

Agent-native (HTTP 402) USDC settlement on Algorand, alongside the escrow contract.

- **x402** = the agent-to-agent payment rail (instant settlement).
- **escrow** (`contracts/`) = the delivery-guarantee rail (held funds, release on proof).
- The buyer agent **chooses** the rail per deal.

> Status: foundation built (`signers.py`, `config.py`, `facilitator_service.py`). Supplier x402 server, buyer client tool, and agent wiring are the next increment. Nothing here is wired into the live agent yet, so the working escrow demo is unaffected.

## Modules

| File | Role | SDK dependency |
|---|---|---|
| `config.py` | USDC ASA id, CAIP-2 network, facilitator URL, algod endpoint | none (pure) |
| `signers.py` | `AlgorandClientSigner` (buyer) + `AlgorandFacilitatorSigner` (settlement) | algosdk only |
| `facilitator_service.py` | FastAPI facilitator: `/verify`, `/settle`, `/supported`, `/health` | x402-avm |

## Install

```bash
pip install "x402-avm[all]"   # already added to requirements.txt
```

### Confirm the import root (one-time)

The skill is inconsistent about whether the package imports as `x402` or `x402_avm`.
`facilitator_service.py` tries both, but confirm which your build uses:

```bash
python - <<'PY'
try:
    import x402; print("import root: x402")
except ImportError:
    import x402_avm; print("import root: x402_avm")
PY
```

If it prints `x402_avm`, the defensive shim already handles it — no edit needed.

## Configure

Add to `.env` (or export):

```bash
# Facilitator signer — reuse the deployer, or set a dedicated base64 64-byte key
ALGORAND_CREATOR_MNEMONIC="<25 words>"     # OR  AVM_PRIVATE_KEY="<base64-64-byte>"

# Stable USDC ASA for x402 (recommended: real testnet USDC, not the per-run mock)
X402_USDC_ASSET_ID=10458941

# Where the supplier server reaches the facilitator
X402_FACILITATOR_URL=http://localhost:4000
ALGOD_SERVER=https://testnet-api.algonode.cloud
```

## Run the facilitator (standalone smoke-test)

```bash
uvicorn x402.facilitator_service:app --port 4000
# then, in another shell:
curl http://localhost:4000/health
curl http://localhost:4000/supported     # should list the Algorand testnet CAIP-2 network
```

If `/supported` returns the testnet network, the facilitator + signer + SDK wiring is good.

## Prerequisites for an end-to-end payment

- The **buyer wallet must be opted into** `X402_USDC_ASSET_ID` and hold enough USDC.
- The **supplier wallet must be opted into** the same USDC ASA to receive payment.
- The facilitator signer needs a little ALGO for fees.

## End-to-end smoke test (one command)

With the facilitator (`:4000`) and supplier server (`:4100`) running, and a
buyer wallet opted into the USDC ASA + funded:

```bash
python x402/smoke_test.py --buyer <buyer-agent-id>
```

It runs pre-flight checks (facilitator reachable; buyer opted-in + funded — the
two most common failures) and then performs the payment, printing the status and
the on-chain settlement `txid`. Success = `status_code: 200`, `fulfilled: true`,
and a txid you can open on the testnet explorer.

## Built so far

| File | Role | Status |
|---|---|---|
| `config.py`, `signers.py` | config + client/facilitator signers | built, verified |
| `facilitator_service.py` | facilitator (`/verify` `/settle` `/supported`) | built |
| `agents/supplier/x402_server.py` | supplier server — payment-gated `/fulfill` priced per deal | built |
| `tools/x402_settle.py` | buyer client — pays + returns txid | built |
| `x402/smoke_test.py` | one-command end-to-end test | built |

## Remaining (gated on a green smoke test)

Buyer agent tool `settle_via_x402(supplier_id)` (9th tool) + prompt guidance on
choosing x402 (instant settlement) vs escrow (delivery guarantee); register in
`agents/buyer/tools.py`. This is the only piece that touches the live agent, so
it waits until the payment path is proven on testnet.
