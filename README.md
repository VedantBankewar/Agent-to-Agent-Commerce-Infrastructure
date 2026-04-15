# AgentTrade — Autonomous Agent-to-Agent Commerce Infrastructure

> Autonomous AI procurement agents that discover suppliers, negotiate deals, and settle payments on the Algorand blockchain — without any human in the loop.    

---

## Table of Contents

1. [The Problem](#the-problem)
2. [Our Solution](#our-solution)
3. [How It Works — The Big Picture](#how-it-works--the-big-picture)
4. [Problems It Solves](#problems-it-solves)
5. [MVP Scope](#mvp-scope)
6. [MVP Explanation](#mvp-explanation)
7. [Tech Stack](#tech-stack)
8. [Features & Functionality](#features--functionality)
9. [Agent Architecture](#agent-architecture)
10. [On-chain vs Off-chain Design](#on-chain-vs-off-chain-design)
11. [Transaction Lifecycle](#transaction-lifecycle)
12. [Project Structure](#project-structure)
13. [Getting Started](#getting-started)
14. [Future Roadmap](#future-roadmap)

---

## The Problem

Autonomous AI agents are increasingly being deployed to manage business operations — scheduling, customer service, data analysis, and more. The next frontier is **agent-to-agent commerce**: AI agents that can independently conduct business transactions on behalf of organizations.

However, this frontier currently lacks trusted infrastructure. Specifically:

- **No trusted negotiation layer** — there is no standard protocol for AI agents to discover each other, exchange structured offers, and negotiate terms without human oversight at every step.
- **No verifiable execution** — when two agents reach an agreement, there is no tamper-proof mechanism to enforce the deal. Either party could back out or alter terms with no consequence.
- **No autonomous payment settlement** — existing payment rails require human authorization. There is no mechanism for agents to lock, hold, and release funds based on real-world conditions being met.
- **No identity or accountability** — agents have no verifiable identities, making it impossible to build trust between them or hold them accountable for transactions.
- **Centralized intermediaries** — all existing B2B procurement platforms rely on centralized systems (marketplaces, payment processors, escrow services) that agents cannot interact with autonomously.

The result: AI agents can think and plan autonomously, but they cannot _transact_ autonomously. Every deal still requires humans to step in at the moment of commitment — defeating the purpose of autonomous agents entirely.

---

## Our Solution

**AgentTrade** is an agent-to-agent commerce infrastructure that enables autonomous AI agents to:

1. **Discover** suppliers through a decentralized marketplace registry
2. **Negotiate** procurement terms — price, quantity, delivery date, warranty — through structured multi-round negotiation
3. **Execute** transactions with payment locked in an Algorand smart contract escrow
4. **Settle** automatically when delivery conditions are verified, without any human involvement

Each agent operates with a **decentralized identity and Algorand wallet**, giving it a verifiable on-chain presence. Agreements are cryptographically signed and anchored on Algorand. Payment flows are enforced by smart contracts — not by trust or manual oversight.

Algorand serves as the **settlement and verification layer** — providing speed (4-second finality), low fees, and the smart contract capabilities needed to make autonomous commerce trustworthy.

---

## How It Works — The Big Picture

```
SME Business Goal
"Buy 50 ergonomic chairs, budget ₹3 lakh, by June 15"
        │
        ▼
┌─────────────────────┐        Negotiate terms         ┌─────────────────────┐
│  Procurement Agent  │ ◄────────────────────────────► │   Supplier Agent    │
│  (Buyer's Robot)    │   RFQ → Quotes → Counter-offer │  (Seller's Robot)   │
│  LangChain + LLM    │                                │  LangChain + LLM    │
│  Algorand Wallet    │                                │  Algorand Wallet    │
└─────────┬───────────┘                                └──────────┬──────────┘
          │  Deal agreed — lock payment                           │
          ▼                                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Algorand Blockchain                                  │
│                                                                             │
│   ┌──────────────────────────────┐                                          │
│   │   Escrow Smart Contract      │  ← Payment locked here                   │
│   │   Locks ALGO until delivery  │  ← Delivery proof submitted here         │
│   │   Auto-releases on proof     │  ← Funds auto-released here              │
│   │   Refunds on timeout         │  ← Buyer protected if delivery fails     │
│   └──────────────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problems It Solves

### 1. Trust between unknown agents

Agents representing different organizations have no reason to trust each other. AgentTrade solves this through **Algorand-based decentralized identities (DIDs)** — each agent has a verifiable wallet address and on-chain transaction history. Trust is cryptographic, not social.

### 2. Payment risk for both parties

Buyers risk paying and never receiving goods. Suppliers risk delivering and never getting paid. The **escrow smart contract** eliminates both risks simultaneously — funds are locked before delivery and released only after verified proof, with an automatic timeout refund if delivery never happens.

### 3. Lack of a standard negotiation protocol

Currently there is no standard for how AI agents should negotiate with each other. AgentTrade defines a **structured JSON-based negotiation protocol** — RFQ, quote, counter-offer, acceptance — that any agent can implement.

### 4. Speed and cost of traditional procurement

Traditional B2B procurement involves emails, phone calls, purchase orders, invoices, and bank transfers — often taking days or weeks. AgentTrade can complete the entire procurement cycle — discovery, negotiation, payment lock, delivery, settlement — in **minutes**, with fees of fractions of a cent on Algorand.

### 5. No audit trail for autonomous transactions

When AI agents make decisions, there is currently no tamper-proof record. AgentTrade anchors **agreement hashes, payment events, and delivery proofs on Algorand** — creating a permanent, verifiable audit trail that neither party can alter.

### 6. Scalability for SMEs

Small and medium enterprises cannot afford dedicated procurement teams. AgentTrade lets an SME deploy a single procurement agent that handles **multiple concurrent supplier negotiations** 24/7, comparing dozens of quotes and executing deals autonomously.

---

## MVP Scope

The MVP demonstrates the **complete end-to-end procurement and settlement loop** with two agent types, a simple marketplace, and Algorand Testnet settlement. It is scoped to prove the core concept without building every production feature.

### What is IN the MVP

| Feature               | Description                                                              |
| --------------------- | ------------------------------------------------------------------------ |
| Procurement Agent     | LangChain ReAct agent with 4 tools: search, RFQ, compare, sign           |
| Supplier Agent(s)     | Two supplier agents with inventory, pricing, and negotiation logic       |
| Agent Marketplace     | SQLite-backed supplier registry with search by category and rating       |
| RFQ System            | Structured request-for-quote broadcast and response collection via Redis |
| Quote Scoring         | Weighted multi-criteria scorer (price, delivery, rating, warranty)       |
| Negotiation           | 2-round counter-offer negotiation between agents                         |
| Algorand Wallet       | Each agent has a generated Algorand Testnet wallet with DID              |
| Escrow Smart Contract | PyTeal contract: lock → deliver → release / timeout refund               |
| Deal Hash Anchoring   | SHA-256 of agreement anchored in Algorand note field                     |
| Delivery Proof        | Simulated delivery proof submission triggering escrow release            |
| Agent Reasoning Log   | LangChain verbose trace saved to log files for demo visibility           |
| Cinematic Dashboard   | High-fidelity autonomous UI with real-time pipeline and bidding comparison |

### What is OUT of the MVP (future roadmap)

| Feature                           | Reason deferred                                               |
| --------------------------------- | ------------------------------------------------------------- |
| IPFS document storage             | Local file system is sufficient for demo                      |
| Real IoT delivery triggers        | Simulated proof is enough to demonstrate the flow             |
| Multi-hop negotiation (>2 rounds) | 2 rounds proves the concept cleanly                           |
| Production PostgreSQL             | SQLite handles hackathon load                                 |
| Agent reputation system           | Placeholder ratings in DB                                     |
| Stablecoin payments               | ALGO sufficient for demo; ASA tokens are a production upgrade |

---

## MVP Explanation

### What happens during a demo run

1. A human operator starts the procurement agent with a single natural-language goal:

   ```
   "Buy 50 ergonomic chairs, budget ₹3,00,000, needed by June 15"
   ```

2. The **procurement agent** reasons through the task autonomously:
   - Searches the supplier registry → finds 3 suppliers
   - Broadcasts an RFQ to the top 2 (by rating)
   - Waits up to 30 seconds for quotes to arrive in Redis
   - Scores all quotes using weighted criteria
   - Selects the best supplier (or triggers tie-break negotiation)

3. The **supplier agent(s)** respond autonomously:
   - Receive the RFQ
   - Check inventory database
   - Calculate a quote (unit price, delivery date, warranty)
   - Send the quote back to the procurement agent
   - If counter-offered, evaluate and respond

4. Both agents agree on terms → the procurement agent calls the **Algorand smart contract**:
   - Locks ALGO payment in escrow
   - Records deal hash on-chain in note field
   - Contract enters "locked" state

5. The supplier agent simulates delivery → submits a **delivery proof hash** to the contract:
   - Contract verifies the hash and deadline
   - Contract transitions to "delivered" state
   - ALGO is automatically released to the supplier wallet

6. The demo dashboard shows the **complete on-chain audit trail**: wallet addresses, escrow lock transaction, delivery proof transaction, and payment release transaction — all verifiable on Algorand Testnet Explorer.

### The negotiation in action

```
Procurement Agent:  "RFQ: 50 chairs, budget ₹2,750/unit, by June 15"

Supplier (FurniCo): "Quote: ₹2,750/unit, 10 days, 2yr warranty"
Supplier (ChairHub): "Quote: ₹2,500/unit, 18 days, 1yr warranty"

Scoring:
  FurniCo  → 87.4  (best balance of price, delivery, rating)
  ChairHub → 70.0  (cheap but slow delivery tanks score)

Procurement Agent selects FurniCo.
→ Signs agreement → Locks ₹1,37,500 (in ALGO) in escrow
→ [10 days later] FurniCo submits delivery proof hash
→ Smart contract releases ALGO to FurniCo wallet automatically
```

---

## Tech Stack

### AI / Agent Layer

| Technology                                   | Role                                                               |
| -------------------------------------------- | ------------------------------------------------------------------ |
| **LangChain (Python)**                       | Agent framework — ReAct loop, tool-calling, memory management      |
| **Claude claude-sonnet-4-20250514 / GPT-4o** | LLM powering agent reasoning and negotiation decisions             |
| **FastAPI**                                  | Exposes each agent as a REST service for inter-agent communication |

### Blockchain Layer

| Technology           | Role                                                                  |
| -------------------- | --------------------------------------------------------------------- |
| **Algorand**         | Settlement blockchain — fast (4s finality), low fees, smart contracts |
| **PyTeal / Beaker**  | Python libraries for writing Algorand smart contracts (AVM)           |
| **algosdk (Python)** | Algorand SDK — wallet creation, transaction signing, contract calls   |
| **Algorand Testnet** | Free test network with fake ALGO for hackathon development            |

### Data Layer

| Technology           | Role                                                                      |
| -------------------- | ------------------------------------------------------------------------- |
| **SQLite**           | Primary relational database — agents, RFQs, quotes, agreements, inventory |
| **Redis**            | Real-time quote collection, agent messaging queue, session state          |
| **Local filesystem** | Agreement documents (JSON), delivery proofs, LLM reasoning logs           |

### Development Tools

| Technology                    | Role                                            |
| ----------------------------- | ----------------------------------------------- |
| **Python 3.11+**              | Primary language across all components          |
| **python-dotenv**             | Environment variable management                 |
| **pytest**                    | Unit and integration testing                    |
| **Algorand Testnet Explorer** | Live on-chain transaction verification for demo |

---

## Features & Functionality

### Procurement Agent

The procurement agent is a LangChain ReAct agent powered by an LLM. It reasons step-by-step through a procurement task and calls tools to act on the world.

**Tools available to the procurement agent:**

```python
search_suppliers(category, max_price, min_rating)
# → Queries supplier registry, returns ranked list with wallet addresses

send_rfq(supplier_ids, item, qty, budget, deadline)
# → Broadcasts RFQ to selected suppliers, opens Redis collection window

compare_quotes(rfq_id, weights)
# → Normalizes and scores all received quotes, returns ranked results

sign_and_lock_escrow(supplier_id, agreed_terms)
# → Signs deal with agent wallet, calls Algorand escrow contract
```

**Scoring formula:**

```
Score = (price_score × 0.40) + (delivery_score × 0.30)
      + (rating_score × 0.20) + (warranty_score × 0.10)

Where each score is normalized to 0–100:
  price_score    = (min_price / supplier_price) × 100
  delivery_score = (min_days / supplier_days) × 100
  rating_score   = (supplier_rating / max_rating) × 100
  warranty_score = (supplier_warranty_yrs / max_warranty_yrs) × 100
```

### Supplier Agent

The supplier agent runs as a listening service, responding to incoming RFQs autonomously.

**Tools available to the supplier agent:**

```python
check_inventory(item, qty, delivery_date)
# → Queries inventory DB, returns availability and dispatch timeline

calculate_quote(item, qty, delivery_date)
# → Computes unit price from base cost + margin + delivery charges

evaluate_counter_offer(rfq_id, counter_terms)
# → Accepts / counters / rejects based on min price floor in system prompt

confirm_and_submit_proof(txn_id, tracking_id, delivered_on)
# → Submits delivery proof hash to Algorand escrow contract
```

**Negotiation rules (in system prompt):**

- Never quote below minimum acceptable price
- Can discount maximum 8% from initial quote
- Meet halfway on first counter, hold firm after that
- Always include delivery date and quote validity window

### Algorand Escrow Smart Contract

The escrow contract is the trust backbone of the system. It enforces the deal conditions without any human involvement.

**Contract states:**

```
IDLE → LOCKED → DELIVERED → COMPLETED
                          ↘ REFUNDED (on timeout)
```

**Contract functions:**

```python
lock_escrow(buyer, supplier, amount, deal_hash, deadline)
# Called by: procurement agent
# Effect: locks ALGO, records deal hash, sets delivery deadline

submit_delivery_proof(rfq_id, delivery_hash)
# Called by: supplier agent
# Effect: records proof hash, transitions state to DELIVERED

release_payment()
# Called by: anyone (permissionless) after DELIVERED state
# Effect: transfers ALGO to supplier wallet, marks COMPLETED

claim_refund()
# Called by: buyer agent after deadline passes without delivery
# Effect: returns ALGO to buyer wallet, marks REFUNDED
```

### Agent Identity & Wallets

Each agent is initialized with an Algorand wallet:

```python
private_key, address = algosdk.account.generate_account()
# address = the agent's on-chain identity (DID equivalent)
# private_key = used to sign all transactions (stored securely off-chain)
```

Agent profiles are stored in SQLite with their wallet address as the identifier, linking on-chain identity to off-chain business metadata (name, category, rating history).

---

## On-chain vs Off-chain Design

### On-chain (Algorand) — permanent, public, tamper-proof

| Data                             | Format                      | When recorded       |
| -------------------------------- | --------------------------- | ------------------- |
| Agent wallet address + DID       | Note field                  | Agent registration  |
| Agreed deal terms hash (SHA-256) | Note field                  | Escrow lock         |
| ALGO payment amount              | Payment transaction         | Escrow lock         |
| Delivery proof hash (SHA-256)    | Note field                  | Delivery submission |
| Contract state transitions       | Smart contract global state | Each state change   |
| Payment release transaction      | Payment transaction         | Auto-release        |
| Timeout refund transaction       | Payment transaction         | Refund trigger      |

### Off-chain — fast, flexible, private

| Data                                   | Storage          | Reason                   |
| -------------------------------------- | ---------------- | ------------------------ |
| Full RFQ messages (item, specs, notes) | SQLite           | Too large + private      |
| Supplier quote breakdowns              | SQLite           | Business-sensitive       |
| Negotiation chat logs                  | SQLite           | Operational data         |
| Full agreement document (JSON)         | Local filesystem | Too large for note field |
| Delivery raw data (tracking, photos)   | Local filesystem | Binary / large files     |
| Inventory & product catalog            | SQLite           | Supplier's private data  |
| LLM reasoning traces                   | Log files        | Debug / demo only        |
| Live quote collection                  | Redis (TTL 30s)  | Temporary, real-time     |
| Agent negotiation session state        | Redis (TTL 5min) | Short-lived              |

### The Hash Bridge Pattern

Full data lives off-chain. Its fingerprint lives on-chain. Anyone can verify integrity.

```python
import hashlib, json

def anchor_agreement(agreement: dict) -> str:
    canonical = json.dumps(agreement, sort_keys=True)
    deal_hash = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    # Store full agreement in local DB / filesystem (off-chain)
    # Anchor only deal_hash in Algorand note field (on-chain)
    return deal_hash

def verify_agreement(agreement: dict, on_chain_hash: str) -> bool:
    return anchor_agreement(agreement) == on_chain_hash
    # True  → data is untampered ✓
    # False → someone modified the agreement ✗
```

---

## Transaction Lifecycle

```
① Agent Registration
   Procurement agent wallet created → address anchored on Algorand

② Supplier Discovery
   Procurement agent → search_suppliers() → SQLite registry
   Returns: [FurniCo (4.8★), ChairHub (4.2★), OfficePro (4.6★)]

③ RFQ Broadcast
   Procurement agent → send_rfq() → FastAPI → Supplier agents
   Redis key opens: rfq:RFQ_991:quotes (TTL: 30s)

④ Quote Collection
   Supplier agents → check_inventory() + calculate_quote()
   → Push quotes to Redis: rfq:RFQ_991:quotes

⑤ Scoring & Selection
   Procurement agent → compare_quotes() → weighted scorer
   FurniCo wins with score 87.4

⑥ Optional Negotiation (if scores within 5 points)
   Procurement agent → counter-offer → Supplier agent
   Supplier agent → evaluate_counter_offer() → accept / counter

⑦ Escrow Lock  [ON-CHAIN]
   Procurement agent → sign_and_lock_escrow()
   → algosdk signs txn → calls PyTeal contract
   → ALGO locked in contract address
   → deal_hash written to Algorand note field
   → Contract state: LOCKED

⑧ Delivery Submission  [ON-CHAIN]
   Supplier agent → confirm_and_submit_proof()
   → delivery_hash written to Algorand note field
   → Contract state: DELIVERED

⑨ Auto-release  [ON-CHAIN]
   Smart contract verifies delivery_hash + deadline
   → ALGO transferred to supplier wallet
   → Contract state: COMPLETED

⑩ Audit Trail
   All on-chain transactions visible on Algorand Testnet Explorer
   All off-chain data verifiable via hash comparison
```

---

## Project Structure

```
AgentTrade/
│
├── agents/
│   ├── procurement_agent.py     # LangChain ReAct agent — buyer side
│   ├── supplier_agent.py        # LangChain ReAct agent — seller side
│   └── prompts/
│       ├── procurement.txt      # System prompt — procurement rules
│       └── supplier.txt         # System prompt — negotiation rules + price floor
│
├── tools/
│   ├── search_suppliers.py      # Tool: query marketplace registry
│   ├── send_rfq.py              # Tool: broadcast RFQ via Redis
│   ├── compare_quotes.py        # Tool: weighted scoring engine
│   ├── sign_escrow.py           # Tool: call Algorand escrow contract
│   ├── check_inventory.py       # Tool: query supplier inventory DB
│   ├── calculate_quote.py       # Tool: compute offer price + margin
│   ├── evaluate_counter.py      # Tool: accept / reject / counter logic
│   └── submit_proof.py          # Tool: anchor delivery proof on Algorand
│
├── contracts/
│   ├── escrow.py                # PyTeal escrow smart contract
│   ├── deploy.py                # Deploy contract to Algorand Testnet
│   └── interact.py             # Helper functions for contract calls
│
├── marketplace/
│   ├── registry.py              # Supplier registry API (FastAPI)
│   └── seed_data.py             # Seed 3 sample suppliers for demo
│
├── db/
│   ├── schema.sql               # SQLite schema — agents, RFQs, quotes, deals
│   └── hackathon.db             # SQLite database file (auto-created)
│
├── messaging/
│   └── redis_client.py          # Redis helpers — push/pop quotes, inbox
│
├── utils/
│   ├── wallet.py                # Algorand wallet creation + signing helpers
│   ├── hashing.py               # SHA-256 deal hash + verification
│   └── logger.py                # LangChain trace logger
│
├── agreements/                  # Off-chain full agreement JSON files
├── delivery/                    # Off-chain delivery proof JSON files
├── logs/                        # LangChain agent reasoning traces
│
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
│
├── demo.py                      # One-command end-to-end demo runner
├── requirements.txt
├── .env.example                 # ANTHROPIC_API_KEY, ALGORAND_TOKEN, REDIS_URL
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js & npm (for the cinematic dashboard)
- Redis (local or Docker)
- Algorand Testnet access (free — no signup needed)

### Installation

```bash
git clone https://github.com/your-username/agentrade.git
cd agentrade
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

### Setup

```bash
# Initialize the SQLite database and seed supplier data
# (This happens automatically in demo.py, but you can run them manually)
python -c "from db.initializedb import init_db; init_db('db/hackathon.db')"
python marketplace/seed_data.py

# Deploy the escrow smart contract to Algorand Testnet
python contracts/deploy.py

# Your .env ALGORAND_CREATOR_MNEMONIC will be used for deploying and funding.
# Ensure the creator wallet has sufficient ALGO.
# Visit: https://bank.testnet.algorand.network/
```

### 4. Run the full End-to-End Pipeline

AgentTrade provides both a visual dashboard and a CLI orchestration flow.

#### A. Launch the Cinematic Dashboard (Recommended)

1. **Start the Backend APIs**:
   ```bash
   # Launch the marketplace registry and event streamer
   uvicorn server:app --port 8000 --reload
   ```

2. **Launch the Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Interact**: Open `http://localhost:5173` to see the autonomous pipeline. Enter a goal like *"Buy 5 ergonomic chairs"* and watch the agent navigate discovery, negotiation, and settlement.

#### B. CLI-only Pipeline

Because the underlying Escrow smart contract is a singleton instance (locks only once), you must execute these three separate scripts to perform a clean Testnet pipeline run:

```bash
# 1. Start with a clean contract state
python contracts/deploy.py

# 2. Negotiate, Purchase, and Lock Escrow (Wipe the DB first as a safeguard)
Remove-Item db/hackathon.db; python demo.py --goal "Buy 5 ergonomic chairs, budget 0.20, by June 15"

# 3. Simulate Delivery & Auto-Release Escrow Funds to Supplier
python release_funds.py
```

If you don't have Redis installed, you can skip the marketplace background service flag during step 2:

```bash
Remove-Item db/hackathon.db; python demo.py --goal "Buy 5 ergonomic chairs, budget 0.20, by June 15" --skip-marketplace
```

### What you will see

The orchestrator provides a beautiful pipeline view of autonomous commerce:

```
════════════════════════════════════════════════════════════
  AGENTTRADE — DEMO STARTUP
════════════════════════════════════════════════════════════
  ✓  ANTHROPIC_API_KEY set
  ✓  Escrow contract deployed — App ID: 758565388
  ✓  Database ready — 6 tables: agents, deals, inventory...
  ✓  Escrow live — App ID: 758565388 | State: IDLE

════════════════════════════════════════════════════════════
  PROCUREMENT PIPELINE
════════════════════════════════════════════════════════════
  🎯  Goal parsed
      item: chair
      quantity: 50
      budget: 10 ALGO
      deadline: 2026-06-15

  📡  Supplier search — 2 found
      • FurniCo  (rating 4.7  base $0.1  lead 14d)
      • ChairHub  (rating 4.2  base $0.08  lead 7d)

  📤  RFQ broadcast to supplier network
      rfq_id: 24b44438-4d7...

  🤖  Supplier agents generating quotes...
    💬  FurniCo quoted $0.12/unit  |  14d delivery  |  3.0yr warranty
    💬  ChairHub quoted $0.09/unit  |  7d delivery  |  2.0yr warranty

  📊  Quotes scored — 2 evaluated
      👑 ChairHub: score=94.5  |  $0.09/unit  |  7d  |  2.0yr

  🏆  Winner: ChairHub
      score: 94.5
      total: $4.72

  🔐  Locking escrow on Algorand Testnet...
  ✓  Escrow LOCKED on Algorand Testnet
    🔗  On-chain details
      deal_id: 0e75d840-b56...
      deal_hash: sha256:a7276127e3...
      txid: NYY7N6FPPXDPFGVOD52YLM...

════════════════════════════════════════════════════════════
  AGENTTRADE — TRANSACTION TRAIL
════════════════════════════════════════════════════════════
  Goal:   Buy 50 ergonomic chairs, budget 10, by June 15
  Status: SUCCESS

  [1]  RFQ Broadcast
       rfq_id=24b44438-4d7...  item=chair  qty=50
  [2]  Quotes Scored
       winner=ChairHub  price=$0.09/unit
  [3]  Deal Agreed
       total=$4.72  delivery=7d  warranty=2.0yr
  Deal Hash:  sha256:ef24210f7afd5280ca3b45917bd2a04ff98978a69ed6fa9400d7112413956455
  Buyer:      75FBJ62IDIZ6RHYN7IHG4RP2KV3KS7B3XN3UQVOC63WVIDELHTYIBCA2IE
  Escrow:     X66VDA5DNDV7EIUKEF2H4RUCBMYIVZY2F2AWBNAD443LFHEWTLPJERRZ2U
  Supplier:   3MI4WW2MQFE473E4G3IPOKM6YT7IKOYUK5VR22QA4AWYM2RCA4OUIWRDUU
```

Executing `python release_funds.py` completes the post-negotiation workflow by finalizing the on-chain logic:

```
[1] Finding locked deal...
    Found deal_id: 00a7aea8-8255-4bb5-9cf2-3946fb1248d5

[2] Generating mock delivery proof...
    Saved delivery proof to delivery\00a7aea8-8255-4bb5-9cf2-3946fb1248d5.json

[2.5] Funding supplier wallet from deployer...
    Supplier wallet funded for transactions.

[3] Submitting delivery proof on-chain (contract -> DELIVERED)...
    txid: OJ346KZNGIQ2VJ2UI556VTNLFBNMCTDKDDY4GIMSAOJN5D3AC6NQ
    proof_hash: sha256:963cc52ff40f2433db80a660c489adf32201826ed19650646b0989b9ba61d8df

[4] Releasing payment on-chain (contract -> COMPLETED)...
    Payment released! txid: LB4NEEHUBRURL4GMFQQRG2QKX2O56HX6J2NA7HSU6UPVSLRAOCOQ

[5] Database updated. Deal 00a7aea8-8255-4bb5-9cf2-3946fb1248d5 is COMPLETED.

Successfully released escrow funds to the supplier!
```

---

## Future Roadmap

### Phase 2 — Production hardening

- IPFS integration for decentralized agreement document storage
- PostgreSQL replacing SQLite for concurrent multi-agent workloads
- ASA (Algorand Standard Assets) stablecoin payments instead of raw ALGO
- Multi-round negotiation (up to 5 rounds with escalating strategies)
- Agent reputation scoring system updated on-chain after each transaction

### Phase 3 — Ecosystem expansion

- Supplier agent onboarding portal — any business can register a supplier agent
- Cross-category procurement — one procurement agent handling multiple RFQs in parallel
- Oracle integration for real delivery verification (Chainlink / custom IoT oracle)
- Agent DAO governance — community-voted marketplace rules and dispute resolution

### Phase 4 — Enterprise features

- Multi-agent procurement committees — multiple buyer agents voting on supplier selection
- Compliance layer — agents that verify regulatory and contractual constraints before signing
- ERP integration — procurement agents that read from and write back to SAP / Tally
- Cross-chain settlement — bridging Algorand escrow to other chains via Wormhole

---

## Why Algorand

| Property                           | Why it matters for AgentTrade                                         |
| ---------------------------------- | --------------------------------------------------------------------- |
| **4-second finality**              | Agents get instant confirmation — no waiting for block confirmations  |
| **Low fees (~0.001 ALGO)**         | Agents can transact frequently without fee costs distorting decisions |
| **PyTeal / Beaker**                | Python-native smart contract development — matches our agent stack    |
| **AVM (Algorand Virtual Machine)** | Deterministic execution — critical for trustless escrow enforcement   |
| **Note fields**                    | Built-in 1KB data anchoring on every transaction — perfect for hashes |
| **Testnet + Faucet**               | Free, fast developer experience for hackathon prototyping             |

---

## Team

Built for **Algorand HackSeries 3** by a team exploring the intersection of autonomous AI agents and decentralized commerce infrastructure.

---

## License

MIT License — open for the community to build on.

---

_AgentTrade — where AI agents shake hands and blockchains keep them honest._
