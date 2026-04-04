# Implementation Workflow — AgentTrade

## Implementation Order (Priority)

Follow this exact sequence. Each phase must be complete before the next begins.

1. **Wallet & identity** — `utils/wallet.py` using `algosdk.account.generate_account()`
2. **SQLite schema** — agents, suppliers, RFQs, quotes, deals
3. **Redis client** — messaging and quote collection
4. **PyTeal escrow contract** — state machine with lock/deliver/release/refund
5. **Contract deploy script** — algosdk to Testnet
6. **Supplier agent tools** — inventory check, quote calculation, counter-offer evaluation, proof submission
7. **Procurement agent tools** — supplier search, RFQ broadcast, quote comparison, escrow signing
8. **LangChain prompts** — system prompts encoding negotiation rules and price floors
9. **FastAPI marketplace** — supplier registry API
10. **Demo runner** — end-to-end orchestration

## Smart Contract Rules

- Every contract function must check state preconditions before executing
- Use `Approve()` / `Reject()` for all branching logic
- Store: buyer address, supplier address, amount, deal_hash, delivery_deadline, state
- State stored as a global UInt (0=IDLE, 1=LOCKED, 2=DELIVERED, 3=COMPLETED, 4=REFUNDED)
- Never store large data on-chain — only hashes

## Database Rules

- All foreign keys must be validated before inserts
- Use transactions for multi-step operations (e.g., creating a deal)
- Timestamps in UTC always
- No hardcoded IDs — use UUIDs or generated keys

## LangChain Agent Rules

- Each agent has its own system prompt file (`agents/prompts/`)
- Never hardcode API keys in agent prompts
- Log all tool calls with arguments and results to `logs/`
- Memory: use ConversationBufferMemory for negotiation context

## API Rules

- All endpoints return JSON
- Use HTTP status codes correctly (200=success, 400=bad request, 404=not found, 500=error)
- Validate all inputs before processing
- No secrets in API responses

## Testing Rules

- Test escrow state transitions in isolation
- Test quote scoring with known inputs to verify formula
- Test negotiation round limits
- Integration test: full happy path from RFQ to payment release
