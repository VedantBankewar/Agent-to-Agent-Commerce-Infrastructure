# Project Architecture Rules — AgentTrade

## Overview

AgentTrade is a **Python-first** hackathon project. The AI agent layer (LangChain + LLM) is Python. The smart contract layer must be compatible with the Python agent stack.

## Stack Commitments (Do Not Change)

- **Primary language**: Python 3.12+
- **Agent framework**: LangChain (Python) — ReAct loop
- **Smart contracts**: PyTeal + algosdk (Python SDK)
- **Blockchain**: Algorand (Testnet for dev, mainnet for prod)
- **Database**: SQLite (agents, RFQs, quotes, deals)
- **Message queue**: Redis (quote collection, TTL 30s; session state, TTL 5min)
- **API**: FastAPI (marketplace registry, inter-agent communication)

## Algorand Tooling Conflict Resolution

**CRITICAL**: There is a conflict between `AGENTS.md` (says "never PyTeal/Beaker") and `CLAUDE.md` (says "use PyTeal/Beaker").

**Resolution for this project**: Use **PyTeal + algosdk (Python)** as documented in CLAUDE.md. Rationale:
- The entire agent stack is Python — PyTeal matches naturally
- The project spec was written around PyTeal
- algosdk is the documented Python SDK for wallet/transaction operations
- This is a hackathon project, not a production codebase — consistency with the spec matters more than chasing the latest tooling

When in doubt, follow CLAUDE.md for this project.

## On-chain / Off-chain Split

**On-chain (Algorand) — permanent, public, tamper-proof only:**
- Agent wallet address (note field on registration)
- Deal terms hash SHA-256 (note field on escrow lock)
- ALGO payment amount (payment transaction)
- Delivery proof hash (note field on delivery)
- Escrow contract global state transitions
- Payment release and refund transactions

**Off-chain — everything else:**
- Full RFQ messages, quote breakdowns, negotiation logs → SQLite
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
| `lock_escrow(buyer, supplier, amount, deal_hash, deadline)` | Procurement agent | Contract in IDLE |
| `submit_delivery_proof(rfq_id, delivery_hash)` | Supplier agent | Contract in LOCKED |
| `release_payment()` | Anyone (permissionless) | Contract in DELIVERED |
| `claim_refund()` | Buyer agent | Contract in LOCKED + deadline passed |

## Directory Structure (Source of Truth)

```
agentrade/              # Root Python package
├── agents/             # LangChain ReAct agents
├── tools/              # Agent tools (search, RFQ, escrow, etc.)
├── contracts/          # PyTeal escrow + deploy scripts
├── marketplace/        # FastAPI supplier registry
├── db/                 # SQLite schema + migrations
├── messaging/          # Redis client helpers
├── utils/             # Wallet, hashing, logging helpers
├── agreements/         # Off-chain agreement JSON
├── delivery/          # Off-chain delivery proof JSON
├── logs/              # LLM reasoning traces
└── demo.py             # End-to-end orchestration
```

**Do not** deviate from this structure without updating CLAUDE.md first.

## Quote Scoring Formula

```
Score = (price_score × 0.40) + (delivery_score × 0.30) + (rating_score × 0.20) + (warranty_score × 0.10)

price_score    = (min_price / supplier_price) × 100
delivery_score = (min_days / supplier_days) × 100
rating_score   = (supplier_rating / max_rating) × 100
warranty_score = (supplier_warranty_yrs / max_warranty_yrs) × 100
```

Implement exactly as above. Weights are fixed for MVP.

## Negotiation Rules

- Maximum 2 rounds of counter-offers
- Supplier never quotes below minimum acceptable price (price floor in system prompt)
- Maximum 8% discount from initial quote
- Meet halfway on first counter, hold firm after
- Always include delivery date and quote validity window in quotes

## Transaction Lifecycle — Follow This Order

1. Agent Registration → wallet created, address anchored on Algorand
2. Supplier Discovery → `search_suppliers()` → SQLite registry
3. RFQ Broadcast → `send_rfq()` → Redis key `rfq:{id}:quotes` (TTL 30s)
4. Quote Collection → supplier agents push quotes to Redis
5. Scoring & Selection → `compare_quotes()` → weighted scorer
6. Optional Negotiation → counter-offer → 2 rounds max
7. Escrow Lock → `sign_and_lock_escrow()` → ALGO locked, deal_hash in note field
8. Delivery Submission → `confirm_and_submit_proof()` → delivery_hash in note field
9. Auto-release → `release_payment()` → ALGO to supplier
10. Audit Trail → all on-chain txns verifiable on Algorand Testnet Explorer

## MVP Scope — What to Build vs Skip

**In scope (implement):**
- LangChain ReAct procurement agent with 4 tools: search, RFQ, compare, sign
- Two supplier agents with inventory, pricing, negotiation logic
- SQLite-backed supplier registry
- Redis-based RFQ broadcast and quote collection
- Weighted multi-criteria quote scorer
- 2-round counter-offer negotiation
- Algorand Testnet wallet per agent
- PyTeal escrow: lock → deliver → release / timeout refund
- SHA-256 deal hash anchoring in Algorand note field
- Simulated delivery proof triggering escrow release
- LangChain trace → log files
- CLI dashboard showing live transaction trail

**Out of scope (do NOT implement):**
- IPFS document storage
- Real IoT delivery triggers
- Multi-hop negotiation (>2 rounds)
- Production PostgreSQL
- Agent reputation system
- Stablecoin (ASA) payments
- Web frontend

## Why These Decisions Were Made

- **Python everywhere**: LangChain is Python-native; matching PyTeal keeps the stack uniform
- **Algorand over other chains**: 4s finality, low fees, Python SDK, note fields for hash anchoring
- **SQLite over PostgreSQL**: Hackathon scale; zero setup; schema is simple
- **Redis for quotes**: TTL-based expiration is perfect for short-lived RFQ windows
- **Hash bridge**: On-chain storage is expensive; hash anchoring gives integrity without the cost
