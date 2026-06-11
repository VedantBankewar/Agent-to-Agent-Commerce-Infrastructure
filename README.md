# AgentTrade — Autonomous Agent-to-Agent Commerce Infrastructure

> An LLM-powered buyer agent that **discovers suppliers, negotiates multi-variable deals, and settles payment in USDC on Algorand** — end-to-end, with no human in the loop after the request.

**Live demo: [https://agent-trade.live](https://agent-trade.live)** · Built for **AlgoBharat Hack Series 3.0**

---

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — three-layer design, buyer agent & tools, negotiation engine, EventBus, transaction lifecycle
- [SMART_CONTRACT.md](SMART_CONTRACT.md) — escrow contract: state machine, on-chain state, operations, permissions, security
- [x402pay/README.md](x402pay/README.md) — x402 (HTTP-native agent payments) layer — install + testnet runbook

---

## The Problem

AI agents can analyze, recommend, and plan — but they cannot **transact** on their own. Three things are missing, and all three must exist together for autonomous commerce to work:

1. **No negotiation protocol** — no standard way for agents to exchange offers and haggle price/delivery/warranty across rounds.
2. **No trust mechanism** — two agents representing two companies that have never met have no basis to trust each other's word.
3. **No autonomous settlement** — no neutral way to lock funds and release them only on delivery, without a human or a marketplace sitting in the middle.

The result: **a human is always required at the most expensive, slowest step — closing the deal.**

---

## Our Solution

A buyer fills one **structured form** (item, quantity, budget, deadline, priority — all in USD). From there an **autonomous buyer agent** runs the entire procurement:

1. **Discovers** suppliers from a marketplace registry
2. **Negotiates** concurrently with multiple suppliers — up to 7 rounds, multi-variable (price, delivery, warranty)
3. **Settles** the winning deal: USDC is locked in an Algorand **escrow** smart contract and the deal hash is anchored on-chain
4. **Releases** payment automatically on delivery proof — or refunds the buyer on timeout

Each agent has an Algorand wallet (its on-chain identity). Trust is enforced by code — escrow + on-chain settlement — not by an intermediary.

```
Buyer (structured form, USD)
        │  POST /api/run_pipeline
        ▼
┌──────────────────────────┐     SupplierInterface (ABC)     ┌──────────────────────────┐
│  Autonomous Buyer Agent  │ ◄─────────────────────────────► │  Supplier (bot / LLM /    │
│  LangGraph ReAct · 8 tools│   RFQ → Quote → Counter → Accept │  human) — all interchangeable│
│  priority-driven strategy │   ≤7 rounds, concurrent          └──────────────────────────┘
└─────────┬────────────────┘
          │  deal agreed — settle in USDC
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Algorand (Testnet)                                    │
│   Escrow (PyTeal): IDLE → LOCKED → DELIVERED → COMPLETED / REFUNDED            │
│   USDC (ASA) locked · deal hash anchored · auto-release on proof · refund on   │
│   timeout · x402 (HTTP-402) agent payment layer (x402pay/)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How a run actually works

1. **Submit** a structured request (e.g. *50 × Ergonomic Office Chair, $15,000, priority = balanced*). No free-text parsing.
2. The **buyer agent** (LangGraph ReAct, 8 tools) discovers suppliers in the category and fires **concurrent RFQs**.
3. It **scores** quotes with priority-weighted weights and **negotiates** with the top suppliers — trading variables when price is stuck, referencing competing offers.
4. It **accepts** the best offer within budget and calls `lock_escrow`: a group transaction transfers USDC into the contract and anchors the SHA-256 deal hash on-chain.
5. The supplier submits a **delivery-proof hash** → contract goes `DELIVERED` → payment **auto-releases** (`COMPLETED`), or the buyer reclaims funds after the deadline (`REFUNDED`).
6. Every round is persisted off-chain (full audit trail); every state transition is verifiable on the Algorand explorer.

Every supplier — deterministic **bot**, **LLM**-powered, or **human**-in-the-loop — speaks the same `SupplierInterface`, so the buyer agent doesn't know or care who's on the other side.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent** | LangChain / **LangGraph** (Python) — ReAct loop, 8 tools, priority-aware prompt |
| **LLM** | DigitalOcean GenAI (`openai-gpt-oss-120b`) primary, with **Groq / Gemini / Anthropic failover** + Groq key rotation |
| **API** | FastAPI — in-process **EventBus → SSE** streaming (typed events) + a verbose-output pipeline for the demo feed |
| **Contracts** | **PyTeal** + algosdk — escrow on the Algorand AVM |
| **Settlement** | **USDC** (Algorand Standard Asset, 1:1 with USD); **x402-avm** for HTTP-native agent payments (`x402pay/`) |
| **Data** | SQLite (agents, suppliers, RFQs, quotes, deals, negotiation sessions/rounds) · Redis (optional; SQLite fallback) · filesystem (agreements, delivery proofs, logs) |
| **Frontend** | React 19 + TypeScript + Vite + Tailwind |
| **Deploy** | Docker (single image) on DigitalOcean + nginx |

---

## Buyer agent — 8 tools

A LangGraph ReAct agent that makes every decision (max 30 iterations):

| Tool | Purpose |
|---|---|
| `discover_suppliers(category)` | Search the marketplace registry |
| `request_quotes(supplier_ids)` | Send RFQs to N suppliers concurrently |
| `evaluate_quotes()` | Score + rank with the priority-weighted formula |
| `send_counter_offer(...)` | Multi-variable counter to one supplier |
| `accept_offer(supplier_id)` | Accept a supplier's terms |
| `reject_supplier(supplier_id, reason)` | Walk away |
| `lock_escrow(supplier_id)` | Lock USDC in the Algorand escrow (1:1 with USD) |
| `get_negotiation_status()` | View all active negotiations |

**Scoring (dynamic weights, driven by the buyer's priority):**

```
Score = price·Wp + delivery·Wd + rating·Wr + warranty·Ww      (each sub-score 0–100)

priority   Wp    Wd    Wr    Ww
cost       0.60  0.15  0.10  0.15
speed      0.20  0.50  0.15  0.15
quality    0.15  0.15  0.35  0.35
balanced   0.40  0.30  0.20  0.10   (default)
```

---

## Escrow smart contract (PyTeal, USDC)

```
IDLE → LOCKED → DELIVERED → COMPLETED
                          ↘ REFUNDED (on timeout)
```

| Function | Caller | Effect |
|---|---|---|
| `lock` | buyer agent | group txn: USDC → contract; records buyer/seller/amount/deal_hash/deadline |
| `deliver` | supplier | records delivery-proof hash, → `DELIVERED` |
| `release` | anyone (permissionless) | inner USDC transfer → supplier, → `COMPLETED` |
| `refund` | buyer (after deadline) | inner USDC transfer → buyer, → `REFUNDED` |

Full data lives off-chain; only its SHA-256 fingerprint is anchored on-chain (Hash Bridge pattern) — see [SMART_CONTRACT.md](SMART_CONTRACT.md).

---

## Project Structure

```
AgentTrade/
├── core/                         # Protocol layer
│   ├── types.py                  # dataclasses, enums, SCORING_WEIGHTS
│   ├── supplier_interface.py     # SupplierInterface ABC + SupplierRegistry
│   ├── negotiation.py            # NegotiationSessionManager (concurrent, persisted)
│   └── events.py                 # EventBus (in-process emitter)
├── agents/
│   ├── buyer/                    # ← critical component: agent.py, tools.py (8), prompts.py
│   └── supplier/                 # bot.py (RuleBot), llm_agent.py (LLM), human.py, x402_server.py
├── tools/                        # calculate_quote, search_suppliers, evaluate_counter,
│                                 #   sign_escrow, submit_proof, x402_settle, ...
├── contracts/                    # escrow.py (PyTeal), deploy.py, interact.py
├── x402pay/                      # x402 (HTTP-402) payment layer: signers, facilitator, config
├── marketplace/                  # registry.py (FastAPI), seed_data.py (suppliers + inventory)
├── db/                           # schema.sql, initializedb.py
├── messaging/redis_client.py
├── utils/                        # wallet.py, hashing.py, logger.py
├── frontend/                     # React + Vite dashboard
├── server.py                     # FastAPI: SSE pipeline + serves the frontend
├── demo.py                       # CLI entry point (autonomous agent)
└── release_funds.py              # delivery proof + payment release
```

> **Live code-walkthrough path (start here):** `agents/buyer/tools.py` (the 8 tools) → `core/negotiation.py` (the concurrent negotiation engine) → `contracts/escrow.py` (the on-chain trust layer).

---

## Getting Started

### Prerequisites
- Python 3.12 · Node.js + npm · Algorand Testnet access (free)
- An LLM key (one of `DO_AI_API_KEY` / `GROQ_API_KEY` / `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`)
- A funded Algorand Testnet creator wallet (ALGO for fees; USDC for settlement)

### Install & configure
```bash
pip install -r requirements.txt
cp .env.example .env
# set in .env: ALGORAND_CREATOR_MNEMONIC, an LLM key, ALGOD_ADDRESS, (optional) USDC_ASSET_ID, REDIS_URL
```
Fund the creator wallet with testnet ALGO (https://bank.testnet.algorand.network/) and, for real-USDC settlement, USDC (https://faucet.circle.com/).

### Run — CLI (one full procurement)
The escrow contract is **single-use** (it locks once), so deploy a fresh one before each CLI run:
```bash
python contracts/deploy.py     # 1. fresh IDLE escrow + USDC opt-in
python demo.py --item "Ergonomic Office Chair" --category furniture --quantity 50 --budget 15000 --priority balanced
python release_funds.py        # 2. submit delivery proof + release payment → COMPLETED
```
`demo.py` auto-seeds suppliers, registers + funds a persistent buyer wallet, tops up its USDC from the deployer, then runs the autonomous agent to `ESCROW LOCKED` with an on-chain TX.

### Run — Web dashboard
```bash
npm --prefix frontend install && npm --prefix frontend run build
python server.py               # serves API + built frontend on http://localhost:8000
```
Open `/deploy`, submit the form, and watch the pipeline stream live (the web path deploys a fresh contract per run automatically).

---

## Live Deployment

Publicly accessible at **[https://agent-trade.live](https://agent-trade.live)**.

| Component | Details |
|---|---|
| Host | DigitalOcean — NYC1, Ubuntu 24.04 LTS · IP 198.199.73.187 |
| Container | Docker `python server.py` on :8000 (`.env` + `keys/` volume-mounted) |
| Proxy | nginx → :443 (Let's Encrypt), SSE buffering disabled |

---

## Why Algorand

| Property | Relevance |
|---|---|
| 4-second finality | Agents get instant settlement confirmation |
| Low fees (~0.001 ALGO) | Frequent agent transactions without fee distortion |
| PyTeal (Python AVM) | Matches the Python agent stack |
| USDC (ASA) | Stablecoin settlement, 1:1 with USD, no FX risk |
| x402 on AVM | HTTP-native agent-to-agent payments |
| Testnet + faucets | Free, fast development |

---

## Roadmap

- **Now:** working testnet MVP — discover → negotiate → USDC escrow settlement → release
- **Next:** full x402 settlement path, on-chain platform fee, multi-tenant state (Postgres + worker queue), indexer-backed read model
- **Later:** supplier onboarding + on-chain reputation, ERP integrations, autonomous supplier agents, multi-chain settlement

---

## Team

Built for **AlgoBharat Hack Series 3.0** — infrastructure for autonomous agent-to-agent commerce.

## License

MIT — open for the community to build on.

_AgentTrade — where AI agents shake hands and blockchains keep them honest._
