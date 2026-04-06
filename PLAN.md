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

## Phase 3 — FastAPI Marketplace & Seed Data ✅ COMPLETED

> **Why first:** Both agent types need to query suppliers before anything else. The marketplace must be running before agents can do anything.

**Period:** 2026-04-06

### Steps Completed

| Step | File | Status |
|------|------|--------|
| 3.1 | `marketplace/registry.py` | Done — FastAPI app with 14 routes (health, suppliers CRUD, rfqs CRUD, quotes, status) |
| 3.2 | `marketplace/seed_data.py` | Done — seeds FurniCo, ChairHub, OfficePro |

### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| GET | `/suppliers` | List all suppliers, filter by category / min_rating |
| GET | `/suppliers/{id}` | Single supplier (404 if not found) |
| POST | `/suppliers` | Register supplier (201, validates required fields) |
| PUT | `/suppliers/{id}` | Update rating/inventory (404 if not found) |
| GET | `/rfqs` | List RFQs, filter by status / agent_id |
| GET | `/rfqs/{id}` | Single RFQ (404 if not found) |
| POST | `/rfqs` | Create RFQ (verifies agent FK, 404 if not found) |
| GET | `/rfqs/{id}/quotes` | Fetch quotes — Redis-first, falls back to SQLite |
| PATCH | `/rfqs/{id}/status` | Status transitions with closed_at stamp |

### Seeded Suppliers

- **FurniCo** — furniture, rating 4.7, base_cost 150, margin 20%, lead 14 days, warranty 3yr
- **ChairHub** — furniture, rating 4.2, base_cost 95, margin 18%, lead 7 days, warranty 2yr
- **OfficePro** — office_supplies, rating 4.5, base_cost 10, margin 25%, lead 3 days, warranty 1yr

### Bug Fixed During Phase 3

- `suppliers.created_at` NOT NULL constraint failed — INSERT wasn't providing created_at.
  Fixed: explicitly set `created_at = datetime.now(timezone.utc).isoformat()` in both create and update.

---

## Phase 4 — Supplier Agent Tools ✅ COMPLETED

> **Why next:** Supplier agents are passive listeners — they respond to RFQs. Their tools must work standalone so they can process incoming requests independently.

**Period:** 2026-04-06

### Steps Completed

| Step | File | Status |
|------|------|--------|
| 4.1 | `tools/check_inventory.py` | Done — SQLite inventory query, returns InventoryResult |
| 4.2 | `tools/calculate_quote.py` | Done — base_cost × (1+margin_pct) + delivery_charge, 30-min validity |
| 4.3 | `tools/evaluate_counter.py` | Done — accept/counter/reject per negotiation rules |
| 4.4 | `tools/submit_proof.py` | Done — hash proof, call on-chain submit_delivery, update deals |

### Implementation Notes

**`tools/check_inventory.py`** — JOINs inventory + suppliers, returns `InventoryResult(available, dispatch_days, stock_count, reserved_qty, unit_cost)`. Not-found → `available=False, stock_count=0`.

**`tools/calculate_quote.py`** — Formula: `unit_price = base_cost × (1 + margin_pct/100) + (unit_cost × 0.02)`. Returns `QuoteResult(unit_price, total_price, delivery_days, warranty_yrs, valid_until)`.

**`tools/evaluate_counter.py`** — Decision rules:
- `≥ initial` → **accept**
- `< price_floor` → **reject**
- `≥ max_acceptable` (8% off) → round 1: meet halfway; round 2: hold firm at max
- `< max_acceptable` + rounds left → counter at midway
- `round_number > 2` (max rounds exceeded) → **reject**

**`tools/submit_proof.py`** — Loads `delivery/{deal_id}.json`, hashes via `anchor_delivery_proof()`, calls `submit_delivery()` on-chain, updates `deals.status='delivered'`, logs txn.

**`utils/wallet.py`** — Added `get_supplier_wallet(supplier_id)` to load `keys/{supplier_id}.json`.

### Bug Fixed During Phase 4

- `evaluate_counter`: `round_number >= MAX_NEGOTIATION_ROUNDS` rejected at round 2 prematurely.
  Fixed to `round_number > MAX_NEGOTIATION_ROUNDS` so round 2 properly counters instead of rejecting.

---

## Phase 5 — Procurement Agent Tools ✅ COMPLETED

> **Why next:** The procurement agent is the active initiator. It searches, broadcasts RFQs, scores quotes, and signs escrow — all tools must be solid before wiring the agent.

**Period:** 2026-04-06

### Steps Completed

| Step | File | Status |
|------|------|--------|
| 5.1 | `tools/search_suppliers.py` | Done — API-first with SQLite fallback, category/rating/item filters, returns SupplierMatch list |
| 5.2 | `tools/send_rfq.py` | Done — API-first with SQLite fallback, Redis quote window (TTL 30s), 30s polling for live quotes, returns RFQResult |
| 5.3 | `tools/compare_quotes.py` | Done — Redis-first with SQLite fallback, weighted multi-criteria scoring, returns CompareResult with winner/runner-up |
| 5.4 | `tools/sign_escrow.py` | Done — anchor_agreement → deal_hash, lock_escrow on-chain, save agreement JSON to `agreements/`, record deal in SQLite |

### Implementation Notes

**`tools/search_suppliers.py`** — Calls `GET /suppliers` on marketplace API with category/rating filters; falls back to direct SQLite query (JOINs inventory+suppliers) when API unreachable. Returns `list[SupplierMatch]` ranked by rating.

**`tools/send_rfq.py`** — Posts RFQ to marketplace API; on API failure falls back to direct SQLite INSERT. Opens Redis quote window via `open_quote_window()` (TTL 30s). Polls Redis for up to 30s collecting supplier quotes. Returns `RFQResult` with `supplier_quotes` list.

**`tools/compare_quotes.py`** — Fetches quotes Redis-first, falls back to SQLite JOIN with supplier metadata. Applies exact CLAUDE.md formula:
```
Score = (min_price/price × 0.40) + (min_days/days × 0.30) + (rating/max × 0.20) + (warranty/max × 0.10)
```
Returns `CompareResult` with `quotes_scored`, `winner`, `runner_up`.

**`tools/sign_escrow.py`** — Builds agreement dict → `anchor_agreement()` → `deal_hash`; calls `lock_escrow()` (group txn: payment + app call); saves `agreements/{deal_id}.json`; inserts deal into SQLite `deals` table. Returns `SignResult` with txid and confirmed round. Pre-chain integrity verified: no orphan records on on-chain failure.

### Bugs Fixed During Phase 5

1. `log_tool_call()` signature — `result` was required but `send_rfq` calls it before result exists. Fixed: made `result` optional with default `None`.
2. `send_rfq` API fallback — exception was propagating instead of falling through to SQLite. Fixed: proper `except` block wrapping SQLite fallback.
3. `send_rfq` SQLite INSERT — missing `created_at` column caused NOT NULL constraint failure. Fixed: added `created_at = datetime.now(timezone.utc).isoformat()` to INSERT.
4. `sign_escrow` missing import — `dataclass` not imported. Fixed: added `from dataclasses import dataclass`.
5. `sign_escrow` schema mismatch — INSERT used wrong column names vs actual `deals` table schema:
   - `buyer_agent_id` → `buyer_id`
   - `total_price` → `total_amount`
   - `deadline_ts` (int Unix timestamp) → `deadline` (ISO string via `datetime.fromtimestamp`)
   - Added `escrow_app_id` (TEXT from config) and `escrow_address` (from config)
   - Added `locked_at = now`

### Verification Results (2026-04-06)

- `search_suppliers`: 3 suppliers found via SQLite fallback, category/rating filters work
- `send_rfq`: RFQ created in DB (status=open), Redis window attempted, quotes_rcvd=0 (Redis down)
- `compare_quotes`: 1 quote scored, winner=ToolTestSup1 at score=100.0
- `sign_escrow`: `deal_hash` anchored correctly; on-chain fails with `AlgodHTTPError: overspend` (buyer wallet has 0 ALGO — expected); pre-chain integrity verified (no orphan deals, no orphan agreement files)

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
✅ marketplace/registry.py          (Phase 3.1)
✅ marketplace/seed_data.py      (Phase 3.2)

✅ tools/check_inventory.py      (Phase 4.1)
✅ tools/calculate_quote.py       (Phase 4.2)
✅ tools/evaluate_counter.py      (Phase 4.3)
✅ tools/submit_proof.py         (Phase 4.4)

✅ tools/search_suppliers.py     (Phase 5.1)
✅ tools/send_rfq.py             (Phase 5.2)
✅ tools/compare_quotes.py       (Phase 5.3)
✅ tools/sign_escrow.py          (Phase 5.4)

□ agents/prompts/procurement.txt (Phase 6.1)
□ agents/prompts/supplier.txt    (Phase 6.2)
□ agents/supplier_agent.py       (Phase 6.3)
□ agents/procurement_agent.py    (Phase 6.4)

□ demo.py                        (Phase 7.1)
```

**Completed: 10 / 14 files.**

---

## Known Issues (Post Phase 5)

- Redis not running — `redis_client.ping()` returns False (expected locally, not installed)
- Buyer wallet (DDIIYCXZWOVIERH7CB5RS2CO2B2JVK2BF6GGVULLHKWPUMF2VEBP6Z2KG4) has 0 ALGO — needs faucet funding before on-chain contract calls
- Python 3.13.7 — `hmac.compare_digest` required (not `hashlib.compare_digest`)

_Follow phases in order: 3 → 4 → 5 → 6 → 7 → 8_
