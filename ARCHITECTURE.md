# AgentTrade — Architecture

> How an autonomous LLM buyer agent discovers suppliers, negotiates deeply, and settles deals
> on Algorand — with the frontend fully decoupled from the agent runtime.

---

## 1. System Overview

```
Buyer (Structured Form — USD)
        │
        ▼
┌─────────────────────────┐
│  Autonomous Buyer Agent │  LangGraph ReAct · 8 tools · LLM-driven decisions
│  Discovers, negotiates, │  Concurrent negotiation with 3+ suppliers
│  locks escrow           │  Priority-based strategy (cost/speed/quality)
└─────────┬───────────────┘
          │  Communicates only via SupplierInterface ABC
          ▼
┌──────────────────────────────────────────────────────┐
│              Supplier Interface Layer                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ RuleBotSuppl │ │ LLMSupplier  │ │ HumanSupplier│ │
│  │ (determinist)│ │ (Claude/GPT) │ │ (API/Redis)  │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────────┬───────────────────────────┘
                           │  Deal agreed — lock USDC payment (1:1 with USD)
                           ▼
┌───────────────────────────────────────────────────────┐
│                  Algorand Blockchain                   │
│   Escrow Smart Contract (PyTeal / AVM)                  │
│   USDC (ASA) locked · deal hash anchored on-chain       │
│   Auto-releases on delivery proof · refunds on timeout  │
└───────────────────────────────────────────────────────┘
```

The escrow contract is documented separately in [SMART_CONTRACT.md](SMART_CONTRACT.md).

---

## 2. Three-Layer Design

AgentTrade is split into three layers so the buyer agent never couples to a concrete
supplier type or to the frontend.

| Layer | Package | Responsibility |
|---|---|---|
| **Core Protocol** | `core/` | Shared types, negotiation state machine, supplier ABC, event bus |
| **Supplier Implementations** | `agents/supplier/` | `RuleBotSupplier`, `LLMSupplier`, `HumanSupplier` — all behind one interface |
| **Autonomous Buyer Agent** | `agents/buyer/` | LangGraph ReAct agent with 8 tools and priority-based strategy |

### Layer 1 — `core/` (Protocol, Types, Event Bus)

| Module | Purpose |
|---|---|
| `core/types.py` | All shared dataclasses & enums — `ProcurementRequest`, `NegotiationTerms`, `NegotiationMessage`, `SupplierNegotiationState`, `ProcurementContext`, and the `NegotiationPhase` / `DealPhase` / `Priority` enums |
| `core/supplier_interface.py` | `SupplierInterface` ABC + `SupplierRegistry` (maps `supplier_id → impl`, falls back to `RuleBotSupplier`) |
| `core/negotiation.py` | `NegotiationSessionManager` — orchestrates concurrent negotiations, scores offers, persists every round |
| `core/events.py` | `EventBus` — in-process emitter; no subscribers means events are no-ops (CLI mode works unchanged) |

### Layer 2 — `agents/supplier/` (Supplier Implementations)

All three implement the same `SupplierInterface` ABC, so the buyer agent cannot tell
them apart.

| Implementation | Behavior |
|---|---|
| `bot.py` — `RuleBotSupplier` | Deterministic pricing & multi-variable negotiation; wraps `tools/calculate_quote.py` and `tools/evaluate_counter.py`. Default for all seeded suppliers. |
| `llm_agent.py` — `LLMSupplier` | Claude/GPT-powered supplier reasoning via a LangGraph agent. |
| `human.py` — `HumanSupplier` | Posts RFQs to Redis and waits for a human response (with timeout → `EXPIRED`). |

### Layer 3 — `agents/buyer/` (Autonomous Buyer Agent)

| Module | Purpose |
|---|---|
| `agents/buyer/tools.py` | The 8 buyer tools, each wrapping `NegotiationSessionManager` |
| `agents/buyer/prompts.py` | System-prompt builder — injects the buyer's request, priority, and scoring weights |
| `agents/buyer/agent.py` | LangGraph ReAct agent factory + `run_buyer_agent()` runner |

---

## 3. The 8 Buyer Tools

| Tool | Purpose |
|---|---|
| `discover_suppliers` | Search the marketplace registry by category |
| `request_quotes` | Send RFQs to N suppliers concurrently |
| `evaluate_quotes` | Score & rank quotes with the priority-weighted formula |
| `send_counter_offer` | Send a multi-variable counter to one supplier |
| `accept_offer` | Accept a supplier's terms |
| `reject_supplier` | Walk away from a negotiation |
| `lock_escrow` | Lock USDC in the Algorand escrow contract |
| `get_negotiation_status` | Inspect all active negotiations |

A run is capped at **30 tool calls** to prevent infinite ReAct loops.

---

## 4. Negotiation Model

- **Up to 7 rounds** per supplier (configurable via `max_rounds`).
- **Multi-variable** — price, delivery days, warranty years, and quantity are all
  negotiable each round.
- **Concurrent** — the buyer agent negotiates with 2–3 suppliers simultaneously.
- **Strategy-driven** — the buyer's `priority` setting (`cost` / `speed` / `quality` /
  `balanced`) shapes both the scoring weights and the agent's trade-off behavior.
- **Supplier rules** — never quote below the price floor, max 8% discount, and trade
  delivery/warranty when price is stuck.
- **Walk-away** — 5+ rounds with no progress, all offers over budget, or two rejections.

### Per-supplier state machine

```
INVITED → QUOTED → NEGOTIATING → ACCEPTED
                              ↘ REJECTED / EXPIRED
```

### Overall deal phases

```
DISCOVERY → QUOTING → NEGOTIATING → AGREED → ESCROW_LOCKED → DELIVERED → COMPLETED
```

### Quote scoring formula (dynamic weights)

```
Score = price_score·W_price + delivery_score·W_delivery
      + rating_score·W_rating + warranty_score·W_warranty

price_score    = (min_price     / supplier_price)        × 100
delivery_score = (min_days      / supplier_days)         × 100
rating_score   = (supplier_rating   / max_rating)        × 100
warranty_score = (supplier_warranty / max_warranty_yrs)  × 100
```

| Priority | W_price | W_delivery | W_rating | W_warranty |
|---|---|---|---|---|
| `cost` | 0.60 | 0.15 | 0.10 | 0.15 |
| `speed` | 0.20 | 0.50 | 0.15 | 0.15 |
| `quality` | 0.15 | 0.15 | 0.35 | 0.35 |
| `balanced` (default) | 0.40 | 0.30 | 0.20 | 0.10 |

---

## 5. Frontend Decoupling (EventBus)

The agent runtime has **zero imports** from `server.py` or `frontend/`.

- The agent emits events through `core/events.py` `EventBus` at every key point.
- `server.py` subscribes to the `EventBus` and translates events into SSE for the
  React frontend.
- In **CLI mode** there are no subscribers, so the events are simply no-ops — the
  agent behaves identically with or without the UI running.

Event types: `agent_started`, `suppliers_discovered`, `quote_received`, `counter_sent`,
`counter_received`, `offer_accepted`, `supplier_rejected`, `escrow_locked`,
`delivery_confirmed`, `payment_released`, `agent_thinking`, `agent_error`.

---

## 6. On-chain vs Off-chain Split

**On-chain (Algorand) — permanent, public, tamper-proof:**

- Agent wallet addresses
- Deal terms hash (SHA-256, in the escrow note/state)
- USDC payment amount (ASA transfer)
- Delivery proof hash (SHA-256)
- Escrow contract state transitions
- Payment release and refund transactions

**Off-chain — fast, flexible, private:**

- Full RFQ messages, quote breakdowns, negotiation transcripts → SQLite
- Negotiation sessions & rounds → SQLite (`negotiation_sessions`, `negotiation_rounds`)
- Full agreement documents → `agreements/`
- Delivery raw data → `delivery/`
- Live quote collection → Redis (TTL 30s); agent session state → Redis (TTL 5min)
- LLM reasoning traces → `logs/`

### Hash Bridge Pattern

Full data lives off-chain; only its fingerprint goes on-chain for verifiability.

```python
def anchor_agreement(agreement: dict) -> str:
    canonical = json.dumps(agreement, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
```

---

## 7. Data Layer

| Store | Role |
|---|---|
| **SQLite** (`db/hackathon.db`) | Agents, suppliers, RFQs, quotes, deals, `negotiation_sessions`, `negotiation_rounds`, inventory |
| **Redis** | Quote collection (TTL 30s), agent session state (TTL 5min), negotiation channels |
| **Local filesystem** | `agreements/`, `delivery/`, `logs/` |

Settlement values: all UI / agent / DB logic is in **USD**; on-chain settlement is in
**USDC** (Algorand Standard Asset, 1:1 with USD — no conversion). The escrow contract
operates internally in micro-USDC (6 decimals). ALGO is still required for transaction
fees.

---

## 8. Transaction Lifecycle

```
① Buyer submits structured form (USD)
② Agent initialization — wallet verified, escrow contract checked, strategy configured
③ Supplier discovery     — discover_suppliers() → SQLite registry
④ Concurrent RFQ/quoting — request_quotes() → SupplierInterface.receive_rfq()
⑤ Quote evaluation       — evaluate_quotes() → priority-weighted scorer
⑥ Deep negotiation       — send_counter_offer() × N rounds × M suppliers (concurrent)
⑦ Deal acceptance        — accept_offer() winner; reject_supplier() losers
⑧ Escrow lock   [ON-CHAIN] — lock_escrow() locks USDC, anchors deal hash
⑨ Delivery proof [ON-CHAIN] — submit_proof() anchors delivery hash → DELIVERED
⑩ Payment release [ON-CHAIN] — release_payment() transfers USDC → COMPLETED
⑪ Audit trail            — on-chain txns on Algorand Testnet Explorer + SQLite transcript
```

See [SMART_CONTRACT.md](SMART_CONTRACT.md) for the on-chain steps (⑧–⑩) in detail.

---

## 9. Tech Stack

| Area | Technology |
|---|---|
| Agent framework | LangChain / LangGraph (Python) — ReAct loop |
| LLM | Claude Sonnet / GPT-4o / DigitalOcean GenAI (`openai-gpt-oss-120b`) |
| API | FastAPI — REST + SSE event streaming |
| Smart contracts | PyTeal + algosdk (Python) |
| Blockchain | Algorand (Testnet) |
| Database | SQLite |
| Message queue | Redis |
| Frontend | React + TypeScript + Vite + Tailwind CSS |
| Tooling | AlgoKit CLI, python-dotenv, pytest |
