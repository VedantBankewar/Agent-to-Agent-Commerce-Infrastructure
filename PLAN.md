# AgentTrade — MVP Implementation Plan

> Build order is strict — each phase unblocks the next. Do not skip ahead.

---

## Phase 1 — Foundation ✅ COMPLETED

**Period:** 2026-04-05 (session: `2026-04-05-phase1-complete-session.tmp`)

### Steps Completed

| Step | File | Status |
|------|------|--------|
| 1.1 | `requirements.txt` | Done — algokit, pyteal 0.26.1, langchain, fastapi, redis, etc. |
| 1.2 | `.env.example` | Done — ANTHROPIC_API_KEY, ALGORAND_TOKEN, REDIS_URL, ESCROW_APP_ID |
| 1.3 | `db/schema.sql` | Done — 6 tables: agents, suppliers, rfqs, quotes, deals, inventory |
| 1.4 | `db/initializedb.py` | Done — verified, hackathon.db created |
| 1.5 | `messaging/redis_client.py` | Done — push_quote, get_quotes, send_message, get_messages, session state |
| 1.6 | `utils/wallet.py` | Done — Algorand wallet generation, address validation, signing |
| 1.7 | `utils/hashing.py` | Done — anchor_agreement, anchor_delivery_proof, verify_*, hmac.compare_digest |
| 1.8 | `utils/logger.py` | Done — structured logging, log_tool_call, log_agent_thought, log_txn |

### Bugs Fixed During Phase 1

1. `algosdk.v2.client.AlgoClient` → `algosdk.v2client.algod.AlgodClient` (newer algosdk API)
2. `hashlib.compare_digest` → `hmac.compare_digest` (Python 3.13 moved it)
3. `pyteal` version conflict: pyteal 0.27.0 requires docstring-parser==0.14.1 but 0.26.1 works

### Known Issues

- Redis not running — `messaging.redis_client.ping()` returns False (expected, Redis not installed locally)
- Python 3.13.7 in use — `hmac.compare_digest` required instead of `hashlib.compare_digest`
- PyTeal pinned to 0.26.1 (not 0.27.0) due to docstring-parser conflict

### Database State

- 6 tables verified: agents, deals, inventory, quotes, rfqs, suppliers
- All correct columns and indexes created
- `hackathon.db` initialized at `db/hackathon.db`

---

## Phase 2 — Smart Contract ✅ COMPLETED

**Period:** 2026-04-05 (post Phase 1)

### Steps Completed

| Step | File | Status |
|------|------|--------|
| 2.1 | `contracts/escrow.py` | Done — PyTeal state machine: IDLE→LOCKED→DELIVERED→COMPLETED/REFUNDED. All 4 handlers: lock, deliver, release, refund. State preconditions enforced with Assert. |
| 2.2 | `contracts/escrow_approval.teal` / `escrow_clear.teal` | Done — Compiled TEAL v8 files |
| 2.3 | `contracts/interact.py` | Done — Full algosdk wrappers: lock_escrow, submit_delivery, release_payment, claim_refund, get_escrow_state, group txn builders, config helpers |
| 2.4 | `contracts/deploy.py` | Done — Compile → on-chain compile → app create → MBR fund → verify. Supports --dry-run, --reset, --network. Writes deploy_config.json |
| 2.5 | `contracts/test_escrow.py` | Done — Tests both happy path and refund path with assertions |
| 2.6 | `contracts/deploy_config.json` | Done — Deployed to Testnet, app_id=758338449 |

### Contract State Machine

```
IDLE → LOCKED → DELIVERED → COMPLETED
                          ↘ REFUNDED (on timeout)
```

### On-chain Deployment

```
App ID:    758338449
Address:   LCYADGNO5ECR3HU4E7S2U7FSZWJ52PFCF7BP4SCOJ4H3CHIUYGTG4GFEA4
Network:   Algorand Testnet
Confirmed: Round 62126919
```

### Verification

- Dry-run compile: ✅ 2111 chars approval TEAL, 30 chars clear TEAL
- Contract responds to state queries: ✅ `get_escrow_state()` works
- Buyer wallet low on testnet ALGO — needs faucet funding before re-running tests

---

## Dependency Chain

```
marketplace/registry.py
        ↓
tools/ (supplier tools + procurement tools)
        ↓
agents/prompts/*.txt + agents/supplier_agent.py + agents/procurement_agent.py
        ↓
demo.py
```

---

## Phase 3 — FastAPI Marketplace & Seed Data

> **Why first:** Both agent types need to query suppliers before anything else. The marketplace must be running before agents can do anything.

### Step 3.1 — `marketplace/registry.py`

| Method | Endpoint            | Purpose                                            |
| ------ | ------------------- | -------------------------------------------------- |
| GET    | `/suppliers`        | List all suppliers, filter by category / rating    |
| GET    | `/suppliers/{id}`   | Get a single supplier's full profile               |
| POST   | `/suppliers`        | Register a supplier (used by `seed_data.py`)       |
| PUT    | `/suppliers/{id}`   | Update supplier rating or inventory                |
| GET    | `/rfqs`             | List all RFQs                                      |
| POST   | `/rfqs`             | Create an RFQ (procurement agent posts here)       |
| GET    | `/rfqs/{id}/quotes` | Fetch all quotes for an RFQ (short-circuits Redis) |

### Step 3.2 — `marketplace/seed_data.py`

- Insert 3 sample suppliers into the SQLite registry
- Supplier names: **FurniCo**, **ChairHub**, **OfficePro**
- Fields to seed: category, rating, wallet address, min acceptable price

---

## Phase 4 — Supplier Agent Tools

> **Why next:** Supplier agents are passive listeners — they respond to RFQs. Their tools must work standalone so they can process incoming requests independently.

### Step 4.1 — `tools/check_inventory.py`

- Query SQLite `inventory` table for item + quantity availability
- Return: `available` (bool), `dispatch_days`, `stock_count`

### Step 4.2 — `tools/calculate_quote.py`

- Compute unit price from base cost, margin, and delivery charges
- Return: `unit_price`, `delivery_days`, `warranty_years`, `quote_validity`
- Formula:
  ```
  unit_price = base_cost × (1 + margin_pct) + delivery_charge_per_unit
  ```

### Step 4.3 — `tools/evaluate_counter.py`

- Accept / counter / reject logic for incoming counter-offers
- Rules:
  - Never go below `price_floor`
  - Maximum 8% discount from initial quote
  - Meet halfway on the first counter, hold firm after that
- Return: `{ decision: "accept" | "counter" | "reject", terms: { ... } }`

### Step 4.4 — `tools/submit_proof.py`

- Read delivery proof JSON from the `delivery/` directory
- Call `utils/hashing.py` → `anchor_delivery_proof()`
- Call `contracts/interact.py` → `submit_delivery()`
- Save proof hash to the SQLite `deals` table

---

## Phase 5 — Procurement Agent Tools

> **Why next:** The procurement agent is the active initiator. It searches, broadcasts RFQs, scores quotes, and signs escrow — all tools must be solid before wiring the agent.

### Step 5.1 — `tools/search_suppliers.py`

- Call marketplace API → `GET /suppliers?category=X&min_rating=Y`
- Return: ranked list of `(supplier_id, name, rating, avg_price)`

### Step 5.2 — `tools/send_rfq.py`

- Call marketplace API → `POST /rfqs`
- Open Redis key: `rfq:{id}:quotes` with TTL of 30 seconds
- Store the RFQ record in SQLite
- Wait up to 30 seconds for supplier responses to arrive via Redis

### Step 5.3 — `tools/compare_quotes.py`

- Fetch all quotes for the RFQ from Redis or the marketplace API
- Apply the scoring formula:

  ```
  Score = (price_score    × 0.40)
        + (delivery_score × 0.30)
        + (rating_score   × 0.20)
        + (warranty_score × 0.10)

  Where each score is normalized to 0–100:
    price_score    = (min_price / supplier_price) × 100
    delivery_score = (min_days  / supplier_days)  × 100
    rating_score   = (supplier_rating / max_rating) × 100
    warranty_score = (supplier_warranty_yrs / max_warranty_yrs) × 100
  ```

- Return: ranked list with scores, declare winner

### Step 5.4 — `tools/sign_escrow.py`

- Build agreement dict: `{ rfq_id, supplier_id, item, qty, price, delivery, warranty }`
- Call `utils/hashing.py` → `anchor_agreement()` → produces `deal_hash`
- Call `contracts/interact.py` → `lock_escrow()` group transaction
- Save the full agreement JSON to the `agreements/` directory
- Record `deal_hash` and `txn_id` in the SQLite `deals` table

---

## Phase 6 — LangChain Prompts & Agent Skeletons

> **Why next:** The prompts encode all business rules. Without them, agents have no logic — they are just empty ReAct loops.

### Step 6.1 — `agents/prompts/procurement.txt`

- Role: procurement agent acting on behalf of an SME buyer
- List of 4 available tools with usage instructions
- Quote scoring formula embedded in the prompt
- Decision rules: select winner, initiate escrow, handle edge cases
- Hard constraint: never expose API keys or private keys in output

### Step 6.2 — `agents/prompts/supplier.txt`

- Role: supplier agent acting on behalf of a seller business
- List of 4 available tools with usage instructions
- Price floor per product category (never quote below this)
- Max 8% discount rule, 2-round negotiation limit
- Meet-halfway rule on first counter, hold firm after
- Quote validity window enforcement

### Step 6.3 — `agents/supplier_agent.py`

- LangChain ReAct agent initialized with `supplier.txt` system prompt
- Attach all 4 supplier tools
- `ConversationBufferMemory` for maintaining negotiation context across rounds
- FastAPI HTTP server listening for incoming RFQ events
- On receiving RFQ → run agent → respond with structured quote

### Step 6.4 — `agents/procurement_agent.py`

- LangChain ReAct agent initialized with `procurement.txt` system prompt
- Attach all 4 procurement tools
- CLI interface accepting a natural-language goal string
- Example input:
  ```
  "Buy 50 ergonomic chairs, budget 300000, by June 15"
  ```

---

## Phase 7 — End-to-End Demo Orchestration

> **Why last:** Everything must be individually tested before wiring together for the hackathon demo.

### Step 7.1 — `demo.py`

One-command runner that orchestrates the full demo:

- Initialize SQLite DB and seed supplier data
- Deploy escrow smart contract to Algorand Testnet (if not already deployed)
- Start supplier agent HTTP servers on separate ports
- Start the marketplace API via uvicorn
- Spawn the procurement agent with a goal from the CLI argument
- Poll Redis and the marketplace API for RFQ responses
- Print a live transaction trail to the terminal:
  ```
  RFQ sent → Quotes received → Escrow locked → Delivered → Payment released
  ```

### Step 7.2 — `utils/logger.py` integration

- Ensure all tools write logs to the `logs/` directory
- Log levels:
  - `DEBUG` — tool arguments and raw results
  - `INFO` — milestones (RFQ sent, quote received, escrow locked, etc.)
- Hard constraint: never log private keys or API keys at any level

---

## Phase 8 — Testing & Polish

> Run these in order. Do not submit without completing Step 8.4.

| Step | Test                         | What to verify                                                   |
| ---- | ---------------------------- | ---------------------------------------------------------------- |
| 8.1  | `contracts/test_escrow.py`   | Fund buyer wallet on Testnet, lock and release escrow end-to-end |
| 8.2  | Quote scoring unit test      | Known inputs → expected scores match formula exactly             |
| 8.3  | Negotiation round limit test | Send 3 counter-offers → verify rejection triggers at round 3     |
| 8.4  | Full dry run                 | RFQ → quotes → escrow lock → delivery proof → payment release    |
| 8.5  | README polish                | Ensure demo instructions match actual `demo.py` output           |

---

## File Checklist

Total files to build for MVP:

```
□ marketplace/registry.py          (Phase 3.1)
□ marketplace/seed_data.py         (Phase 3.2)

□ tools/check_inventory.py         (Phase 4.1)
□ tools/calculate_quote.py         (Phase 4.2)
□ tools/evaluate_counter.py        (Phase 4.3)
□ tools/submit_proof.py            (Phase 4.4)

□ tools/search_suppliers.py        (Phase 5.1)
□ tools/send_rfq.py                (Phase 5.2)
□ tools/compare_quotes.py          (Phase 5.3)
□ tools/sign_escrow.py             (Phase 5.4)

□ agents/prompts/procurement.txt   (Phase 6.1)
□ agents/prompts/supplier.txt      (Phase 6.2)
□ agents/supplier_agent.py         (Phase 6.3)
□ agents/procurement_agent.py      (Phase 6.4)

□ demo.py                          (Phase 7.1)
□ utils/logger.py                  (Phase 7.2)
```

**Total: 16 files to MVP.**

---

_Follow phases in order: 3 → 4 → 5 → 6 → 7 → 8_
