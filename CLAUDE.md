# CLAUDE.md — AgentTrade

## Project Overview

**AgentTrade** is an autonomous agent-to-agent commerce infrastructure for the Algorand blockchain. It enables AI agents to discover suppliers, negotiate procurement terms, and settle payments — entirely without human involvement.

- **Type**: Hackathon project (Algorand HackSeries 3)
- **Stack**: Python 3.11+ · LangChain · FastAPI · Algorand (PyTeal/Beaker/algosdk) · SQLite · Redis
- **Status**: Spec-complete, not yet implemented
- **Primary goal**: Demonstrate end-to-end autonomous procurement: RFQ → negotiation → escrow lock → delivery → payment release

---

## Architecture

### System Components

```
SME Business Goal
        │
        ▼
┌─────────────────────┐        Negotiate terms        ┌─────────────────────┐
│  Procurement Agent  │ ◄────────────────────────────► │   Supplier Agent    │
│  (Buyer's Robot)    │   RFQ → Quotes → Counter-offer │  (Seller's Robot)   │
│  LangChain + LLM    │                                │  LangChain + LLM    │
│  Algorand Wallet    │                                │  Algorand Wallet    │
└─────────┬───────────┘                                └──────────┬──────────┘
          │  Deal agreed — lock payment                           │
          ▼                                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Algorand Blockchain                                   │
│   ┌──────────────────────────────┐                                          │
│   │   Escrow Smart Contract      │  ← Payment locked here                   │
│   │   Locks ALGO until delivery  │  ← Delivery proof submitted here         │
│   │   Auto-releases on proof     │  ← Funds auto-released here              │
│   │   Refunds on timeout         │  ← Buyer protected if delivery fails     │
│   └──────────────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent Types

| Agent                 | Role                              | Tools                                                                                      |
| --------------------- | --------------------------------- | ------------------------------------------------------------------------------------------ |
| **Procurement Agent** | Buyer-side LangChain ReAct agent  | `search_suppliers`, `send_rfq`, `compare_quotes`, `sign_and_lock_escrow`                   |
| **Supplier Agent**    | Seller-side LangChain ReAct agent | `check_inventory`, `calculate_quote`, `evaluate_counter_offer`, `confirm_and_submit_proof` |

### On-chain vs Off-chain Split

**On-chain (Algorand) — permanent, public, tamper-proof**

- Agent wallet address + DID (note field on registration)
- Agreed deal terms hash SHA-256 (note field on escrow lock)
- ALGO payment amount (payment transaction)
- Delivery proof hash (note field on delivery)
- Escrow contract state transitions (global state)
- Payment release and refund transactions

**Off-chain — fast, flexible, private**

- Full RFQ messages, quote breakdowns, negotiation logs → SQLite
- Full agreement documents → local filesystem
- Inventory and product catalog → SQLite per supplier
- Live quote collection → Redis (TTL 30s)
- Agent session state → Redis (TTL 5min)
- LLM reasoning traces → log files

### Hash Bridge Pattern

Full data lives off-chain; only its fingerprint lives on-chain for verifiability.

```python
def anchor_agreement(agreement: dict) -> str:
    canonical = json.dumps(agreement, sort_keys=True)
    deal_hash = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    return deal_hash

def verify_agreement(agreement: dict, on_chain_hash: str) -> bool:
    return anchor_agreement(agreement) == on_chain_hash
```

### Escrow Contract State Machine

```
IDLE → LOCKED → DELIVERED → COMPLETED
                          ↘ REFUNDED (on timeout)
```

| Function                                                    | Caller                       | Effect                                       |
| ----------------------------------------------------------- | ---------------------------- | -------------------------------------------- |
| `lock_escrow(buyer, supplier, amount, deal_hash, deadline)` | Procurement agent            | Locks ALGO, records deal hash, sets deadline |
| `submit_delivery_proof(rfq_id, delivery_hash)`              | Supplier agent               | Records proof, transitions to DELIVERED      |
| `release_payment()`                                         | Anyone (permissionless)      | Transfers ALGO to supplier, marks COMPLETED  |
| `claim_refund()`                                            | Buyer agent (after deadline) | Returns ALGO to buyer, marks REFUNDED        |

### Quote Scoring Formula

```
Score = (price_score × 0.40) + (delivery_score × 0.30) + (rating_score × 0.20) + (warranty_score × 0.10)

price_score    = (min_price / supplier_price) × 100
delivery_score = (min_days / supplier_days) × 100
rating_score   = (supplier_rating / max_rating) × 100
warranty_score = (supplier_warranty_yrs / max_warranty_yrs) × 100
```

### Negotiation Rules

- Never quote below minimum acceptable price
- Maximum 8% discount from initial quote
- Meet halfway on first counter, hold firm after
- Always include delivery date and quote validity window
- 2 rounds maximum

---

## Tech Stack

### AI / Agent Layer

| Technology                 | Role                                        |
| -------------------------- | ------------------------------------------- |
| **LangChain (Python)**     | ReAct loop, tool-calling, memory            |
| **Claude Sonnet / GPT-4o** | LLM reasoning                               |
| **FastAPI**                | REST services for inter-agent communication |

### Blockchain Layer

| Technology           | Role                                                 |
| -------------------- | ---------------------------------------------------- |
| **Algorand**         | Settlement — 4s finality, low fees, smart contracts  |
| **PyTeal / Beaker**  | Smart contract authoring (AVM)                       |
| **algosdk (Python)** | Wallet creation, transaction signing, contract calls |
| **Algorand Testnet** | Free test network                                    |

### Data Layer

| Technology           | Role                                                   |
| -------------------- | ------------------------------------------------------ |
| **SQLite**           | Agents, RFQs, quotes, deals, inventory                 |
| **Redis**            | Quote collection, agent messaging queue, session state |
| **Local filesystem** | Agreements, delivery proofs, LLM logs                  |

### Development Tools

| Technology        | Role                                            |
| ----------------- | ----------------------------------------------- |
| **AlgoKit CLI**   | Project scaffolding, LocalNet, deployment       |
| **VibeKit**       | AI agent configuration for Algorand development |
| **python-dotenv** | Environment variable management                 |
| **pytest**        | Testing                                         |

---

## VibeKit

**What it is**: An AI-native CLI tool that configures AI coding agents (Claude Code, Cursor, VS Code) with Algorand-specific skills and tools.

**Why it matters for AgentTrade**: VibeKit provides 44 blockchain operation MCPs covering contracts, assets, accounts, state, and indexer queries. It also enforces security-first key management — private keys never touch the AI, instead using HashiCorp Vault or OS keyring.

**Installation**: `curl -fsSL https://getvibekit.ai/install | sh`

**Key capabilities**:

- One-command setup: `vibekit init`
- Documentation MCPs: Kappa (Algorand docs) or Context7
- Development MCPs: deploy, call, introspect contracts; create/transfer assets; fund/switch/send accounts; query global/local state and boxes; search indexer
- Secure signing: keys in Vault/Keychain, AI requests transactions without seeing keys

**How to use**: Run `vibekit init` in the project directory. It detects available AI tools and configures skills automatically.

- Docs: [getvibekit.ai](https://www.getvibekit.ai/)
- GitHub: [github.com/gabrielkuettel/vibekit](https://github.com/gabrielkuettel/vibekit)

---

## AlgoKit

**What it is**: The official Algorand developer toolkit — CLI + SDK libraries for Python and TypeScript.

**Why it matters for AgentTrade**: AlgoKit is the standard way to scaffold Algorand projects, run a local blockchain (LocalNet), and deploy smart contracts. It wraps `algosdk` with higher-level utilities.

**Key commands**:

```bash
algokit init              # Create new Algorand project
algokit localnet start    # Run local Algorand blockchain
algokit deploy            # Deploy contracts to network
algokit account create    # Generate wallet
```

**Core library**: `algorand` (TypeScript) / `algokit` (Python) provides `AlgorandClient` with manager classes for accounts, assets, and contracts.

**How to use**: Install via `npm install -g @algorandfoundation/algokit-cli` or `pip install algokit`.

- Docs: [developer.algorand.org/docs/get-details/algokit/tutorials/intro](https://developer.algorand.org/docs/get-details/algokit/tutorials/intro/)
- GitHub: [github.com/algorandfoundation/algokit-cli](https://github.com/algorandfoundation/algokit-cli)

---

## Project Structure

```
AgentTrade/
├── agents/
│   ├── procurement_agent.py     # LangChain ReAct — buyer side
│   ├── supplier_agent.py        # LangChain ReAct — seller side
│   └── prompts/
│       ├── procurement.txt      # System prompt — procurement rules
│       └── supplier.txt          # System prompt — negotiation rules + price floor
├── tools/
│   ├── search_suppliers.py      # Query marketplace registry
│   ├── send_rfq.py              # Broadcast RFQ via Redis
│   ├── compare_quotes.py        # Weighted scoring engine
│   ├── sign_escrow.py           # Call Algorand escrow contract
│   ├── check_inventory.py       # Query supplier inventory
│   ├── calculate_quote.py       # Compute offer price + margin
│   ├── evaluate_counter.py      # Accept / reject / counter logic
│   └── submit_proof.py          # Anchor delivery proof on Algorand
├── contracts/
│   ├── escrow.py                # PyTeal escrow smart contract
│   ├── deploy.py                # Deploy to Algorand Testnet
│   └── interact.py             # Contract call helpers
├── marketplace/
│   ├── registry.py              # Supplier registry API (FastAPI)
│   └── seed_data.py             # Seed sample suppliers
├── db/
│   ├── schema.sql               # SQLite schema
│   └── hackathon.db             # Database file (auto-created)
├── messaging/
│   └── redis_client.py          # Redis helpers
├── utils/
│   ├── wallet.py                # Algorand wallet creation + signing
│   ├── hashing.py               # SHA-256 deal hash + verification
│   └── logger.py                # LangChain trace logger
├── agreements/                  # Off-chain agreement JSON files
├── delivery/                    # Off-chain delivery proof JSON files
├── logs/                        # LLM reasoning traces
├── .claude/                     # Claude Code configuration and memory
│   ├── settings.json           # Claude Code hooks and behavior config
│   ├── memory/                 # Persistent memory files
│   ├── sessions/               # Session history and state
│   ├── contexts/               # Project context files
│   ├── skills/                 # Claude Code skill definitions
│   ├── hooks/                  # Claude Code hook scripts
│   └── rules/                  # Claude Code rule files
│
├── CLAUDE.md                    # Claude Code project context and guidelines
├── demo.py                      # One-command end-to-end demo
├── requirements.txt
├── .env.example
└── README.md
```

---

## Transaction Lifecycle

```
① Agent Registration
   Wallet created → address anchored on Algorand

② Supplier Discovery
   search_suppliers() → SQLite registry
   Returns: ranked suppliers with wallet addresses

③ RFQ Broadcast
   send_rfq() → FastAPI → Supplier agents
   Redis key opens: rfq:{id}:quotes (TTL: 30s)

④ Quote Collection
   Supplier agents → check_inventory() + calculate_quote()
   → Push quotes to Redis

⑤ Scoring & Selection
   compare_quotes() → weighted scorer

⑥ Optional Negotiation (if scores within 5 points)
   Counter-offer → accept / counter → 2 rounds max

⑦ Escrow Lock  [ON-CHAIN]
   sign_and_lock_escrow()
   → ALGO locked in contract
   → deal_hash written to note field
   → Contract state: LOCKED

⑧ Delivery Submission  [ON-CHAIN]
   confirm_and_submit_proof()
   → delivery_hash written to note field
   → Contract state: DELIVERED

⑨ Auto-release  [ON-CHAIN]
   release_payment()
   → ALGO transferred to supplier
   → Contract state: COMPLETED

⑩ Audit Trail
   All on-chain txns verifiable on Algorand Testnet Explorer
```

---

## MVP Scope

### In Scope

| Feature               | Description                                              |
| --------------------- | -------------------------------------------------------- |
| Procurement Agent     | LangChain ReAct with 4 tools: search, RFQ, compare, sign |
| Supplier Agents       | Two agents with inventory, pricing, negotiation logic    |
| Agent Marketplace     | SQLite-backed supplier registry                          |
| RFQ System            | Redis-based broadcast and collection                     |
| Quote Scoring         | Weighted multi-criteria scorer                           |
| Negotiation           | 2-round counter-offer                                    |
| Algorand Wallet       | Generated Testnet wallet with DID per agent              |
| Escrow Smart Contract | PyTeal: lock → deliver → release / timeout refund        |
| Deal Hash Anchoring   | SHA-256 in Algorand note field                           |
| Delivery Proof        | Simulated proof triggering escrow release                |
| Agent Reasoning Log   | LangChain trace → log files                              |
| CLI Dashboard         | Live transaction trail                                   |

### Out of Scope (Future)

- IPFS document storage
- Real IoT delivery triggers
- Multi-hop negotiation (>2 rounds)
- Production PostgreSQL
- Agent reputation system
- Stablecoin (ASA) payments
- Web frontend

---

## Why Algorand

| Property                       | Relevance                                           |
| ------------------------------ | --------------------------------------------------- |
| 4-second finality              | Agents get instant confirmation                     |
| Low fees (~0.001 ALGO)         | Frequent transactions without fee distortion        |
| PyTeal / Beaker                | Python-native smart contracts — matches agent stack |
| AVM (Algorand Virtual Machine) | Deterministic execution for trustless escrow        |
| Note fields (1KB)              | Built-in data anchoring for hashes                  |
| Testnet + Faucet               | Free, fast hackathon dev experience                 |

---

## Implementation Priorities

1. **Wallet & identity** — `utils/wallet.py` using `algosdk.account.generate_account()`
2. **SQLite schema** — agents, suppliers, RFQs, quotes, deals
3. **Redis client** — messaging and quote collection
4. **PyTeal escrow contract** — state machine with lock/deliver/release/refund
5. **Contract deploy script** — AlgoKit or algosdk to Testnet
6. **Supplier agent tools** — inventory check, quote calculation, counter-offer evaluation, proof submission
7. **Procurement agent tools** — supplier search, RFQ broadcast, quote comparison, escrow signing
8. **LangChain prompts** — system prompts encoding negotiation rules and price floors
9. **FastAPI marketplace** — supplier registry API
10. **Demo runner** — end-to-end orchestration
