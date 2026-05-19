# CLAUDE.md — AgentTrade v2

## Project Overview

**AgentTrade** is an autonomous procurement platform where an LLM-powered buyer agent negotiates with suppliers (bots, LLM agents, or humans) and settles deals on the Algorand blockchain — entirely without human involvement after the buyer submits a request.

- **Type**: Hackathon project (Algorand HackSeries 3)
- **Stack**: Python 3.12+ · LangChain/LangGraph · FastAPI · Algorand (PyTeal/algosdk) · SQLite · Redis · React/TypeScript
- **Branch**: `autonomous-agent` (v2 rethink), `main` (v1 legacy)
- **Status**: v1 complete (scripted pipeline), v2 in progress (autonomous agent)
- **Primary goal**: Buyer fills a structured form (USD), autonomous agent discovers suppliers, negotiates deeply (5-7 rounds, multi-variable), and locks Algorand escrow

---

## Architecture

### System Overview

```
Buyer (Structured Form — USD)
        │
        ▼
┌─────────────────────────┐
│  Autonomous Buyer Agent │  LangGraph ReAct · 8 tools · LLM-driven decisions
│  Discovers, negotiates, │  Concurrent negotiation with 3+ suppliers
│  locks escrow            │  Priority-based strategy (cost/speed/quality)
└─────────┬───────────────┘
          │  Communicates via SupplierInterface ABC
          ▼
┌──────────────────────────────────────────────────────┐
│              Supplier Interface Layer                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ RuleBotSuppl │ │ LLMSupplier  │ │ HumanSupplier│ │
│  │ (determinist)│ │ (Claude/GPT) │ │ (API/Redis)  │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────────┬───────────────────────────┘
                           │  Deal agreed — lock payment (USD → ALGO conversion)
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Algorand Blockchain                                   │
│   ┌──────────────────────────────┐                                          │
│   │   Escrow Smart Contract      │  ← ALGO locked (converted from USD)      │
│   │   PyTeal state machine       │  ← Deal hash anchored on-chain           │
│   │   Auto-releases on proof     │  ← Delivery proof triggers release       │
│   │   Refunds on timeout         │  ← Buyer protected if delivery fails     │
│   └──────────────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Three Architecture Layers

| Layer | Package | Purpose |
|---|---|---|
| **Core Protocol** | `core/` | Shared types, negotiation state machine, supplier ABC, event bus |
| **Supplier Implementations** | `agents/supplier/` | RuleBotSupplier, LLMSupplier, HumanSupplier — all implement same interface |
| **Autonomous Buyer Agent** | `agents/buyer/` | LangGraph ReAct agent with 8 tools, priority-based strategy |

### Buyer Agent Tools (8 total)

| Tool | Purpose |
|---|---|
| `discover_suppliers` | Search marketplace by category |
| `request_quotes` | Send RFQ to N suppliers concurrently |
| `evaluate_quotes` | Score and rank using priority-weighted formula |
| `send_counter_offer` | Multi-variable counter to one supplier |
| `accept_offer` | Accept supplier's terms |
| `reject_supplier` | Walk away from negotiation |
| `lock_escrow` | Convert USD → ALGO, lock on Algorand |
| `get_negotiation_status` | View all active negotiations |

### Supplier Types

| Type | Implementation | When Used |
|---|---|---|
| **RuleBotSupplier** | Deterministic pricing + negotiation logic | Default for all seeded suppliers |
| **LLMSupplier** | LangChain agent with Claude/GPT reasoning | When supplier wants AI-powered responses |
| **HumanSupplier** | Redis/API adapter, waits for human input | When supplier is a real person |

### On-chain vs Off-chain Split

**On-chain (Algorand) — permanent, public, tamper-proof:**
- Agent wallet addresses
- Deal terms hash SHA-256 (note field on escrow lock)
- ALGO payment amount (converted from USD at lock time)
- Delivery proof hash (note field on delivery)
- Escrow contract state transitions
- Payment release and refund transactions

**Off-chain — fast, flexible, private:**
- Full RFQ messages, quote breakdowns, negotiation transcripts → SQLite
- Full agreement documents → local filesystem (`agreements/`)
- Delivery raw data → local filesystem (`delivery/`)
- Negotiation sessions and rounds → SQLite
- Inventory and product catalog → SQLite per supplier
- Live quote collection → Redis (TTL 30s)
- Agent session state → Redis (TTL 5min)
- LLM reasoning traces → log files (`logs/`)

### Hash Bridge Pattern

Full data lives off-chain; only its fingerprint lives on-chain for verifiability.

```python
def anchor_agreement(agreement: dict) -> str:
    canonical = json.dumps(agreement, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
```

### Escrow Contract State Machine

```
IDLE → LOCKED → DELIVERED → COMPLETED
                          ↘ REFUNDED (on timeout)
```

| Function | Caller | Effect |
|---|---|---|
| `lock_escrow(buyer, supplier, amount, deal_hash, deadline)` | Buyer agent | Locks ALGO (converted from USD), records deal hash |
| `submit_delivery_proof(rfq_id, delivery_hash)` | Supplier | Records proof, transitions to DELIVERED |
| `release_payment()` | Anyone (permissionless) | Transfers ALGO to supplier, marks COMPLETED |
| `claim_refund()` | Buyer agent (after deadline) | Returns ALGO to buyer, marks REFUNDED |

---

## USD-First Pricing

- **All UI, agent communication, database values, and negotiation in USD**
- Buyer sets budget in USD, sees prices in USD, negotiation happens in USD
- **Conversion to ALGO only at escrow lock time** via configurable rate
- The escrow contract operates in microALGO internally
- Store `usd_to_algo_rate` in the deal record for auditability
- Buyer never sees ALGO unless they click the Algorand explorer link

---

## Structured Buyer Input (No Free Text)

The buyer fills a structured form instead of typing free text. No regex parsing.

**Required Fields:**
| Field | Backend Key | Type |
|---|---|---|
| Product Name | `item` | Text, non-empty |
| Category | `category` | Enum: furniture, office_supplies, electronics, general |
| Quantity | `quantity` | Integer > 0 |
| Max Budget (USD) | `budget_usd` | Float > 0 |
| Delivery Deadline | `deadline` | ISO 8601 date |

**Optional Fields:**
| Field | Backend Key | Default |
|---|---|---|
| Target Price/Unit (USD) | `target_price_usd` | `null` (agent discovers market rate) |
| Minimum Warranty | `min_warranty_yrs` | 1 year |
| Priority | `priority` | `balanced` |
| Special Requirements | `requirements` | `""` |

---

## Quote Scoring Formula

Weights are **dynamic**, driven by buyer's priority setting:

| Priority | Price | Delivery | Rating | Warranty |
|---|---|---|---|---|
| `cost` | 0.60 | 0.15 | 0.10 | 0.15 |
| `speed` | 0.20 | 0.50 | 0.15 | 0.15 |
| `quality` | 0.15 | 0.15 | 0.35 | 0.35 |
| `balanced` | 0.40 | 0.30 | 0.20 | 0.10 |

```
Score = (price_score × w_price) + (delivery_score × w_delivery) + (rating_score × w_rating) + (warranty_score × w_warranty)

price_score    = (min_price / supplier_price) × 100
delivery_score = (min_days / supplier_days) × 100
rating_score   = (supplier_rating / max_rating) × 100
warranty_score = (supplier_warranty_yrs / max_warranty_yrs) × 100
```

---

## Negotiation Rules (v2 — Deep Negotiation)

- **Up to 7 rounds** per supplier (configurable via `max_rounds`)
- **Multi-variable**: price, delivery days, warranty years, quantity — all negotiable each round
- **Concurrent**: buyer agent negotiates with 2-3 suppliers simultaneously
- **Strategy-driven**: agent uses buyer's priority to decide trade-offs
- **Supplier rules**: never below price floor, max 8% discount, multi-variable levers when price is stuck
- **Walk-away conditions**: 5+ rounds with no progress, all offers exceed budget, supplier rejects twice

---

## Tech Stack

### AI / Agent Layer

| Technology | Role |
|---|---|
| **LangChain / LangGraph (Python)** | ReAct loop, tool-calling, agent orchestration |
| **Claude Sonnet / GPT-4o** | LLM reasoning for buyer agent and LLM suppliers |
| **FastAPI** | REST services, SSE streaming, marketplace API |

### Blockchain Layer

| Technology | Role |
|---|---|
| **Algorand** | Settlement — 4s finality, low fees, smart contracts |
| **PyTeal** | Smart contract authoring (AVM) |
| **algosdk (Python)** | Wallet creation, transaction signing, contract calls |
| **Algorand Testnet** | Free test network |

### Data Layer

| Technology | Role |
|---|---|
| **SQLite** | Agents, suppliers, RFQs, quotes, deals, negotiations |
| **Redis** | Quote collection, agent messaging, negotiation channels |
| **Local filesystem** | Agreements, delivery proofs, LLM logs |

### Frontend

| Technology | Role |
|---|---|
| **React + TypeScript** | Buyer dashboard, structured form, live negotiation view |
| **Vite** | Build tool |
| **Tailwind CSS** | Styling |

### Development Tools

| Technology | Role |
|---|---|
| **AlgoKit CLI** | Project scaffolding, LocalNet, deployment |
| **VibeKit** | AI agent configuration for Algorand development |
| **python-dotenv** | Environment variable management |
| **pytest** | Testing |

---

## Project Structure (v2)

```
AgentTrade/
├── core/                        # NEW — Protocol layer
│   ├── __init__.py
│   ├── types.py                 # Shared types: NegotiationTerms, ProcurementRequest, enums
│   ├── supplier_interface.py    # SupplierInterface ABC + SupplierRegistry
│   ├── negotiation.py           # NegotiationSessionManager (state machine, persistence)
│   └── events.py                # EventBus (decouples agent from frontend)
│
├── agents/
│   ├── buyer/                   # NEW — Autonomous buyer agent
│   │   ├── __init__.py
│   │   ├── agent.py             # LangGraph ReAct agent factory + runner
│   │   ├── tools.py             # 8 buyer tools wrapping session manager
│   │   └── prompts.py           # System prompt builder (priority-aware)
│   ├── supplier/                # NEW — Supplier implementations
│   │   ├── __init__.py
│   │   ├── bot.py               # RuleBotSupplier (deterministic)
│   │   ├── llm_agent.py         # LLMSupplier (Claude/GPT-powered)
│   │   └── human.py             # HumanSupplier (API/Redis adapter)
│   ├── procurement_agent.py     # DEPRECATED — v1 scripted agent
│   ├── supplier_agent.py        # DEPRECATED — v1 supplier agent
│   └── prompts/                 # DEPRECATED — v1 prompts
│       ├── procurement.txt
│       └── supplier.txt
│
├── tools/                       # Reused by v2 via supplier/buyer wrappers
│   ├── search_suppliers.py
│   ├── send_rfq.py
│   ├── compare_quotes.py
│   ├── sign_escrow.py
│   ├── check_inventory.py
│   ├── calculate_quote.py
│   ├── evaluate_counter.py      # Extended: multi-round, multi-variable
│   └── submit_proof.py
│
├── contracts/                   # Unchanged
│   ├── escrow.py                # PyTeal escrow smart contract
│   ├── deploy.py                # Deploy to Algorand Testnet
│   └── interact.py              # Contract call helpers
│
├── marketplace/                 # Unchanged
│   ├── registry.py              # Supplier registry API (FastAPI)
│   └── seed_data.py             # Seed sample suppliers
│
├── db/
│   ├── schema.sql               # Extended: + negotiation_sessions, negotiation_rounds
│   ├── initializedb.py
│   └── hackathon.db             # Auto-created
│
├── messaging/
│   └── redis_client.py          # Extended: + negotiation channel helpers
│
├── utils/
│   ├── wallet.py                # Unchanged
│   ├── hashing.py               # Unchanged
│   └── logger.py                # Extended: + log_negotiation_event()
│
├── frontend/                    # React app — decoupled via EventBus
│   └── src/
│       └── components/
│           ├── DeployAgent.tsx   # Updated: structured form, negotiation timeline, USD
│           └── ProcurementForm.tsx  # NEW: structured input form
│
├── agreements/                  # Off-chain agreement JSON files
├── delivery/                    # Off-chain delivery proof JSON files
├── keys/                        # Wallet key files (gitignored)
├── logs/                        # LLM reasoning traces
│
├── CLAUDE.md                    # This file
├── IMPLEMENTATION_PLAN.md       # Detailed v2 implementation plan
├── demo.py                      # Rewritten: autonomous agent entry point
├── server.py                    # Rewritten: EventBus SSE streaming
├── release_funds.py             # Delivery proof + payment release
├── requirements.txt
├── .env.example
└── README.md
```

---

## Transaction Lifecycle (v2)

```
① Buyer submits structured form (USD)
   Product, quantity, budget, deadline, priority, target price

② Agent Initialization
   Wallet verified, escrow contract checked, strategy configured

③ Supplier Discovery
   discover_suppliers() → SQLite registry
   Returns: ranked suppliers with ratings and capabilities

④ Concurrent RFQ & Quoting
   request_quotes() → SupplierInterface.receive_rfq() for each supplier
   Suppliers respond via their implementation (bot/LLM/human)

⑤ Quote Evaluation
   evaluate_quotes() → priority-weighted scorer

⑥ Deep Negotiation (5-7 rounds, multi-variable)
   send_counter_offer() → SupplierInterface.receive_counter()
   Agent negotiates price, delivery, warranty concurrently with top suppliers
   All rounds persisted in negotiation_sessions + negotiation_rounds tables

⑦ Deal Acceptance
   accept_offer() → winning supplier confirmed
   reject_supplier() → losing suppliers notified

⑧ Escrow Lock  [ON-CHAIN]
   lock_escrow() → USD → ALGO conversion → ALGO locked in contract
   deal_hash anchored on-chain, usd_to_algo_rate recorded

⑨ Delivery Proof  [ON-CHAIN]
   submit_proof() → delivery_hash anchored on-chain
   Contract state: DELIVERED

⑩ Payment Release  [ON-CHAIN]
   release_payment() → ALGO transferred to supplier
   Contract state: COMPLETED

⑪ Audit Trail
   All on-chain txns verifiable on Algorand Testnet Explorer
   Full negotiation transcript in SQLite
```

---

## Frontend Decoupling

The agent system is fully decoupled from the frontend via `core/events.py`:

- **EventBus**: In-process event emitter. Agent emits events at key points.
- **server.py**: Subscribes to EventBus, translates events to SSE for frontend.
- **CLI mode**: No subscribers — events are no-ops. Agent works perfectly without frontend.
- **Zero imports**: Agent code has no imports from `server.py` or `frontend/`.

Event types: `agent_started`, `suppliers_discovered`, `quote_received`, `counter_sent`, `counter_received`, `offer_accepted`, `supplier_rejected`, `escrow_locked`, `delivery_confirmed`, `payment_released`, `agent_thinking`, `agent_error`.

---

## Scope

### In Scope (v2)

| Feature | Description |
|---|---|
| Autonomous Buyer Agent | LangGraph ReAct with 8 tools, LLM-driven decisions |
| Structured USD Input | Form with required + optional fields, presets |
| Supplier Interface ABC | Uniform interface for bot/LLM/human suppliers |
| RuleBotSupplier | Deterministic pricing + multi-variable negotiation |
| LLMSupplier | Claude/GPT-powered supplier reasoning |
| HumanSupplier | API/Redis adapter for human-in-the-loop |
| Deep Negotiation | Up to 7 rounds, multi-variable, concurrent |
| Priority-Based Strategy | Cost/Speed/Quality affects scoring weights and agent behavior |
| USD → ALGO Conversion | All USD in UI, conversion at escrow lock time |
| Negotiation Persistence | negotiation_sessions + negotiation_rounds in SQLite |
| EventBus Decoupling | Agent works CLI-only; frontend subscribes to events |
| React Dashboard | Structured form, bidding grid, negotiation timeline, escrow details |
| Algorand Escrow | PyTeal: lock → deliver → release / timeout refund |
| Hash Bridge | SHA-256 deal + delivery hashes anchored on-chain |

### Out of Scope (Future)

- IPFS / Arweave document storage
- Real IoT delivery triggers / logistics oracles
- On-chain reputation system
- Stablecoin (USDC ASA) payments
- Multi-sig procurement committees
- Milestone / split-funding escrow models
- Production PostgreSQL

---

## Why Algorand

| Property | Relevance |
|---|---|
| 4-second finality | Agents get instant confirmation |
| Low fees (~0.001 ALGO) | Frequent transactions without fee distortion |
| PyTeal | Python-native smart contracts — matches agent stack |
| AVM | Deterministic execution for trustless escrow |
| Note fields (1KB) | Built-in data anchoring for hashes |
| Testnet + Faucet | Free, fast development experience |

---

## Implementation Priorities (v2)

1. **Core foundation** — `core/types.py`, `core/supplier_interface.py`, `core/events.py`, `core/negotiation.py`
2. **Supplier implementations** — `agents/supplier/bot.py`, `llm_agent.py`, `human.py`
3. **Database extension** — negotiation_sessions + negotiation_rounds tables
4. **Buyer agent** — `agents/buyer/tools.py`, `prompts.py`, `agent.py`
5. **Extend existing tools** — multi-round evaluate_counter, negotiation Redis channels
6. **Integration** — rewrite `demo.py` + `server.py`
7. **Frontend** — structured form, negotiation timeline, USD display
8. **Testing** — unit tests + integration test (buyer + 3 bots → escrow)

See `IMPLEMENTATION_PLAN.md` for the complete detailed plan.
