# Implementation Workflow — AgentTrade v2

## Implementation Order (Priority)

Follow this exact sequence. Each phase must be complete before the next begins.

1. **Core foundation** — `core/types.py`, `core/supplier_interface.py`, `core/events.py`, `core/negotiation.py`
2. **Supplier implementations** — `agents/supplier/bot.py`, `agents/supplier/llm_agent.py`, `agents/supplier/human.py`
3. **Database extension** — Add `negotiation_sessions` + `negotiation_rounds` tables, extend `deals` with `amount_usd`, `usd_to_algo_rate`
4. **Buyer agent** — `agents/buyer/tools.py` (8 tools), `agents/buyer/prompts.py`, `agents/buyer/agent.py`
5. **Extend existing tools** — `tools/evaluate_counter.py` (multi-round, multi-variable), `messaging/redis_client.py`, `utils/logger.py`
6. **Integration & demo** — Rewrite `demo.py` (structured input, autonomous agent), rewrite `server.py` (EventBus SSE)
7. **Frontend** — `ProcurementForm.tsx` (structured form), update `DeployAgent.tsx` (negotiation timeline, USD display)
8. **Testing & verification** — Unit tests (core types, negotiation state machine), integration test (buyer + 3 bot suppliers → full deal)

## Smart Contract Rules

- Every contract function must check state preconditions before executing
- Use `Approve()` / `Reject()` for all branching logic
- Store: buyer address, supplier address, amount, deal_hash, delivery_deadline, state
- State stored as a global UInt (0=IDLE, 1=LOCKED, 2=DELIVERED, 3=COMPLETED, 4=REFUNDED)
- Never store large data on-chain — only hashes
- Contract operates in microALGO; USD → ALGO conversion happens in `lock_escrow` tool

## Database Rules

- All foreign keys must be validated before inserts
- Use transactions for multi-step operations (e.g., creating a deal + negotiation session)
- Timestamps in UTC always
- No hardcoded IDs — use UUIDs or generated keys
- Negotiation rounds table stores every message exchanged (full audit trail)
- Store USD amounts in negotiation_rounds; ALGO amounts only in deals table after escrow lock

## LangChain/LangGraph Agent Rules

- Buyer agent uses LangGraph ReAct with 8 tools
- System prompt is dynamically built from `ProcurementRequest` (priority, budget, requirements)
- Never hardcode API keys in agent prompts
- Log all tool calls with arguments and results to `logs/`
- Maximum 30 tool calls per agent run (prevents infinite loops)
- Agent emits events via `EventBus` — never imports from `server.py` or `frontend/`

## Supplier Interface Rules

- All supplier types implement `SupplierInterface` ABC
- `SupplierRegistry` maps supplier_id → implementation; falls back to `RuleBotSupplier`
- Buyer agent communicates only through `SupplierInterface` — never directly calls supplier tools
- Bot suppliers wrap existing tools (`calculate_quote`, `evaluate_counter`)
- LLM suppliers wrap existing `supplier_agent.py` LangGraph agent

## Negotiation Rules

- Up to 7 rounds per supplier (configurable `max_rounds`)
- Multi-variable: price, delivery days, warranty years, quantity adjustments
- Concurrent negotiation with 3+ suppliers via `NegotiationSessionManager`
- Per-supplier state machine: INVITED → QUOTED → NEGOTIATING → ACCEPTED/REJECTED/EXPIRED
- Overall deal phases: DISCOVERY → QUOTING → NEGOTIATING → AGREED → ESCROW_LOCKED → DELIVERED → COMPLETED
- Every message persisted to `negotiation_rounds` table

## API Rules

- All endpoints return JSON
- Use HTTP status codes correctly (200=success, 400=bad request, 404=not found, 500=error)
- Validate all inputs before processing (structured `ProcurementRequest` fields)
- No secrets in API responses
- SSE streaming via EventBus subscription (not subprocess stdout)
- API contract: `POST /api/run_pipeline` accepts structured JSON (item, category, quantity, budget_usd, deadline, etc.)

## Testing Rules

- Test escrow state transitions in isolation
- Test quote scoring with known inputs for each priority setting (cost, speed, quality, balanced)
- Test negotiation round limits (7 rounds max)
- Test multi-variable trade-offs (price floor → delivery/warranty trades)
- Test concurrent multi-supplier negotiation
- Integration test: full happy path from structured form → discovery → negotiation → escrow lock → delivery → payment release
- Decoupling test: agent runs correctly with server.py stopped (CLI mode)
