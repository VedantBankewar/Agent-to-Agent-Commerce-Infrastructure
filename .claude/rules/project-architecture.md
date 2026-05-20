# Project Architecture Rules — AgentTrade v2

## Overview

AgentTrade is a **Python-first** autonomous agent-to-agent commerce infrastructure. An LLM-powered buyer agent autonomously discovers suppliers, negotiates deeply (5-7 rounds, multi-variable), and settles payments via Algorand escrow using USDC (ASA). All business logic uses USD; settlement is in USDC (1:1 with USD).

## Stack Commitments (Do Not Change)

- **Primary language**: Python 3.12+
- **Agent framework**: LangChain/LangGraph (Python) — ReAct loop
- **Smart contracts**: PyTeal + algosdk (Python SDK)
- **Blockchain**: Algorand (Testnet for dev, mainnet for prod)
- **Database**: SQLite (agents, RFQs, quotes, deals, negotiation sessions/rounds)
- **Message queue**: Redis (quote collection, TTL 30s; session state, TTL 5min; negotiation channels)
- **API**: FastAPI (marketplace registry, SSE event streaming)
- **Frontend**: React (decoupled via EventBus — removable without breaking agent)

## Algorand Tooling Conflict Resolution

**CRITICAL**: There is a conflict between `AGENTS.md` (says "never PyTeal/Beaker") and `CLAUDE.md` (says "use PyTeal/Beaker").

**Resolution for this project**: Use **PyTeal + algosdk (Python)** as documented in CLAUDE.md. Rationale:
- The entire agent stack is Python — PyTeal matches naturally
- The project spec was written around PyTeal
- algosdk is the documented Python SDK for wallet/transaction operations
- This is a hackathon project — consistency with the spec matters more than chasing latest tooling

When in doubt, follow CLAUDE.md for this project.

## Three-Layer Architecture

### Layer 1: `core/` — Protocol, Types, Event Bus
- `core/types.py` — All shared dataclasses and enums (ProcurementRequest, NegotiationTerms, NegotiationMessage, etc.)
- `core/supplier_interface.py` — SupplierInterface ABC + SupplierRegistry
- `core/negotiation.py` — NegotiationSessionManager (orchestrates concurrent negotiations)
- `core/events.py` — EventBus (in-process emitter; no subscribers = no-ops in CLI mode)

### Layer 2: `agents/supplier/` — Supplier Implementations
- `agents/supplier/bot.py` — RuleBotSupplier (wraps existing tools: calculate_quote, evaluate_counter)
- `agents/supplier/llm_agent.py` — LLMSupplier (wraps LangGraph agent for LLM-powered suppliers)
- `agents/supplier/human.py` — HumanSupplier (posts to Redis, waits for human response)

### Layer 3: `agents/buyer/` — Autonomous Buyer Agent
- `agents/buyer/tools.py` — 8 buyer tools (discover, request_quotes, evaluate, counter, accept, reject, lock_escrow, get_status)
- `agents/buyer/prompts.py` — System prompt builder incorporating buyer's request and priority
- `agents/buyer/agent.py` — LangGraph ReAct agent factory + runner

**Key principle**: The buyer agent communicates through `SupplierInterface` ABC. It never knows if the other side is a bot, an LLM, or a human.

## USD/USDC Settlement

- All UI, agent communication, and database values in **USD**
- Buyer sets budget in USD, sees prices in USD, negotiation happens in USD
- **Settlement in USDC** (Algorand Standard Asset) — 1:1 with USD, no conversion needed
- The escrow contract operates in micro-USDC (6 decimals) internally
- A mock USDC ASA is created during deployment for testnet/demo
- ALGO is still needed for transaction fees on Algorand

## On-chain / Off-chain Split

**On-chain (Algorand) — permanent, public, tamper-proof only:**
- Agent wallet address (note field on registration)
- Deal terms hash SHA-256 (note field on escrow lock)
- USDC payment amount (ASA transfer)
- Delivery proof hash (note field on delivery)
- Escrow contract global state transitions
- Payment release and refund transactions

**Off-chain — everything else:**
- Full RFQ messages, quote breakdowns, negotiation logs → SQLite
- Negotiation sessions and rounds → SQLite
- Full agreement documents → local filesystem (`agreements/`)
- Delivery raw data → local filesystem (`delivery/`)
- Inventory and product catalog → SQLite per supplier
- Live quote collection → Redis (TTL 30s)
- Agent session state → Redis (TTL 5min)
- LLM reasoning traces → log files (`logs/`)

**Never** anchor large data on-chain. Use the Hash Bridge Pattern:

```python
def anchor_agreement(agreement: dict) -> str:
    canonical = json.dumps(agreement, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
```

## Escrow Contract State Machine

```
IDLE → LOCKED → DELIVERED → COMPLETED
                          ↘ REFUNDED (on timeout)
```

| Function | Caller | Precondition |
|---|---|---|
| `lock_escrow(buyer, supplier, amount, deal_hash, deadline)` | Buyer agent | Contract in IDLE |
| `submit_delivery_proof(rfq_id, delivery_hash)` | Supplier | Contract in LOCKED |
| `release_payment()` | Anyone (permissionless) | Contract in DELIVERED |
| `claim_refund()` | Buyer agent | Contract in LOCKED + deadline passed |

## Directory Structure (Source of Truth)

```
AgentTrade/
├── core/                        # Protocol layer
│   ├── __init__.py
│   ├── types.py                 # All shared dataclasses and enums
│   ├── supplier_interface.py    # SupplierInterface ABC + SupplierRegistry
│   ├── negotiation.py           # NegotiationSessionManager
│   └── events.py                # EventBus (in-process emitter)
├── agents/
│   ├── buyer/                   # Autonomous buyer agent
│   │   ├── __init__.py
│   │   ├── agent.py             # LangGraph ReAct agent factory + runner
│   │   ├── tools.py             # 8 buyer tools
│   │   └── prompts.py           # System prompt builder
│   ├── supplier/                # Supplier implementations
│   │   ├── __init__.py
│   │   ├── bot.py               # RuleBotSupplier (deterministic)
│   │   ├── llm_agent.py         # LLMSupplier (LLM-powered)
│   │   └── human.py             # HumanSupplier (human-in-the-loop)
│   ├── procurement_agent.py     # [DEPRECATED] v1 scripted buyer
│   ├── supplier_agent.py        # [DEPRECATED] v1 supplier agent
│   └── prompts/
│       ├── procurement.txt      # [DEPRECATED] v1 prompt
│       └── supplier.txt         # [DEPRECATED] v1 prompt
├── tools/                       # Shared tool implementations
│   ├── search_suppliers.py
│   ├── send_rfq.py
│   ├── compare_quotes.py
│   ├── sign_escrow.py
│   ├── check_inventory.py
│   ├── calculate_quote.py
│   ├── evaluate_counter.py      # Extended: multi-round, multi-variable
│   └── submit_proof.py
├── contracts/
│   ├── escrow.py                # PyTeal escrow smart contract (unchanged)
│   ├── deploy.py
│   └── interact.py
├── marketplace/
│   ├── registry.py
│   └── seed_data.py
├── db/
│   ├── schema.sql               # Extended: negotiation_sessions + negotiation_rounds
│   └── initializedb.py
├── messaging/
│   └── redis_client.py          # Extended: negotiation channel helpers
├── utils/
│   ├── wallet.py
│   ├── hashing.py
│   └── logger.py                # Extended: negotiation event logging
├── frontend/                    # React dashboard (decoupled via EventBus)
│   └── src/components/
│       ├── DeployAgent.tsx       # Updated: structured form, negotiation timeline
│       └── ProcurementForm.tsx   # New: structured input form
├── agreements/
├── delivery/
├── logs/
├── server.py                    # EventBus-based SSE streaming
├── demo.py                      # Rewritten: structured input, autonomous agent
├── IMPLEMENTATION_PLAN.md       # Full v2 implementation plan
└── CLAUDE.md
```

**Do not** deviate from this structure without updating CLAUDE.md first.

## Quote Scoring Formula (Dynamic Weights)

```
Score = (price_score × W_price) + (delivery_score × W_delivery) + (rating_score × W_rating) + (warranty_score × W_warranty)

price_score    = (min_price / supplier_price) × 100
delivery_score = (min_days / supplier_days) × 100
rating_score   = (supplier_rating / max_rating) × 100
warranty_score = (supplier_warranty_yrs / max_warranty_yrs) × 100
```

**Weights are dynamic, driven by buyer's priority setting:**

| Priority | W_price | W_delivery | W_rating | W_warranty |
|---|---|---|---|---|
| `cost` | 0.60 | 0.15 | 0.10 | 0.15 |
| `speed` | 0.20 | 0.50 | 0.15 | 0.15 |
| `quality` | 0.15 | 0.15 | 0.35 | 0.35 |
| `balanced` (default) | 0.40 | 0.30 | 0.20 | 0.10 |

## Negotiation Rules

- **Up to 7 rounds** per supplier (configurable via `max_rounds`)
- **Multi-variable**: price, delivery days, warranty years, quantity adjustments
- **Concurrent**: Agent negotiates with 3+ suppliers simultaneously
- **Strategy-driven**: Agent uses buyer's priority to guide trade-offs
- Supplier never quotes below minimum acceptable price (price floor)
- Maximum 8% discount from initial quote for bot suppliers
- When price hits floor: supplier can trade delivery (-1d, min 3d) or warranty (+0.5yr, max +2yr)
- Agent can walk away, play suppliers against each other, trade variables
- Always include delivery date and warranty in every offer

## Supplier Interface Contract

All supplier types implement `SupplierInterface` ABC:

```python
class SupplierInterface(ABC):
    supplier_id: str
    supplier_name: str

    @abstractmethod
    def receive_rfq(self, message: NegotiationMessage) -> NegotiationMessage: ...

    @abstractmethod
    def receive_counter(self, message: NegotiationMessage) -> NegotiationMessage: ...

    @abstractmethod
    def confirm_deal(self, message: NegotiationMessage) -> NegotiationMessage: ...
```

`SupplierRegistry` maps `supplier_id → SupplierInterface`. Falls back to `RuleBotSupplier` for unregistered suppliers.

## EventBus Decoupling

- `core/events.py` provides in-process event emitter
- Agent emits events at key points (discovery, quote, counter, accept, escrow)
- `server.py` subscribes to EventBus and translates to SSE for frontend
- CLI mode: no subscribers, events are no-ops
- **Agent code has zero imports from `server.py` or `frontend/`**

## Structured Input (No Free Text)

Buyer provides structured `ProcurementRequest` with typed fields:

**Required**: item, category, quantity, budget_usd, deadline
**Optional**: target_price_usd, min_warranty_yrs, priority, requirements

The `parse_procurement_goal()` regex parser from v1 is eliminated entirely.

## Transaction Lifecycle — Follow This Order

1. Agent Deployed → buyer wallet funded, escrow contract verified
2. Supplier Discovery → `discover_suppliers(category)` → SQLite registry
3. RFQ Broadcast → `request_quotes(supplier_ids)` → concurrent via SupplierInterface
4. Quote Evaluation → `evaluate_quotes()` → priority-weighted scorer
5. Deep Negotiation → `send_counter_offer()` × N rounds × M suppliers (concurrent)
6. Offer Acceptance → `accept_offer(supplier_id)` → best scoring offer within budget
7. Escrow Lock → `lock_escrow(supplier_id)` → USDC locked (1:1 with USD), deal_hash in note field
8. Delivery Submission → supplier submits proof → delivery_hash in note field
9. Payment Release → `release_payment()` → USDC to supplier
10. Audit Trail → all on-chain txns verifiable on Algorand Testnet Explorer

## v2 Scope — What to Build vs Skip

**In scope (implement):**
- Autonomous LangGraph ReAct buyer agent with 8 tools
- SupplierInterface ABC with 3 implementations (bot, LLM, human)
- NegotiationSessionManager for concurrent multi-supplier negotiations
- Deep negotiation: 5-7 rounds, multi-variable (price, delivery, warranty)
- USD pricing with USDC settlement (1:1, no conversion)
- Structured form input (ProcurementRequest dataclass)
- Priority-based dynamic scoring weights
- EventBus for frontend decoupling
- SQLite negotiation_sessions + negotiation_rounds tables
- React dashboard: structured form, negotiation timeline, USD display
- PyTeal escrow: lock → deliver → release / timeout refund (unchanged)
- CLI + web modes (EventBus makes both work)

**Out of scope (do NOT implement):**
- IPFS document storage
- Real IoT delivery triggers
- Production PostgreSQL
- On-chain reputation system
- Milestone/split-funding escrow models

## Why These Decisions Were Made

- **Python everywhere**: LangChain/LangGraph is Python-native; matching PyTeal keeps the stack uniform
- **Algorand over other chains**: 4s finality, low fees, Python SDK, note fields for hash anchoring
- **SQLite over PostgreSQL**: Hackathon scale; zero setup; schema is simple
- **Redis for quotes**: TTL-based expiration is perfect for short-lived RFQ windows
- **Hash bridge**: On-chain storage is expensive; hash anchoring gives integrity without the cost
- **USDC settlement**: Real businesses price in USD; USDC (1:1 stablecoin) eliminates exchange rate risk
- **SupplierInterface ABC**: Uniform protocol lets the buyer agent work with any supplier type without coupling
- **EventBus**: Frontend is optional — agent runs identically in CLI and web modes
- **Dynamic scoring weights**: Different buyers have different priorities; one-size-fits-all weights produce suboptimal decisions
