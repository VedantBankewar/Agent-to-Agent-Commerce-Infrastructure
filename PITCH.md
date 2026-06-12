# AgentTrade — Business & Pitch Pack

> Infrastructure for autonomous B2B commerce: AI agents that **negotiate, execute, and settle** procurement agreements without a centralized trust intermediary.

This is the judge- and investor-facing narrative. It is deliberately opinionated and grounded in what is actually built (working testnet MVP), not aspiration. Numbers labeled *(est.)* are directional, not audited.

> **Companion docs:** build plan → [FINAL_PLAN.md](FINAL_PLAN.md) · sourced market/TAM/unit-economics deep-dive → [BUSINESS_CASE.md](BUSINESS_CASE.md) · semifinal deck → [DECK.md](DECK.md). Keep in sync — when a build phase changes what's true (e.g. the on-chain fee in §7 ships), update the matching section here.

---

## 1. One-liner

**AgentTrade lets a buyer's AI agent autonomously discover suppliers, negotiate a multi-variable deal, and settle it in escrow on-chain — closing the one step today's AI can't: the transaction itself.**

Not an AI procurement chatbot. Not a blockchain demo. **Settlement infrastructure for agent-to-agent commerce.**

---

## 2. The problem

AI agents today can *recommend* a supplier but cannot *close* with one. Three things are missing, and all three have to exist together for autonomous commerce to work:

1. **No negotiation protocol** — agents can't haggle price/delivery/warranty across rounds.
2. **No trust mechanism** — two agents representing two companies that have never met have no reason to trust each other's word.
3. **No autonomous settlement** — there's no neutral way to lock funds and release them only on delivery, without a human or a marketplace sitting in the middle.

The result: **a human is always required at the most expensive, slowest step — closing the deal.**

### Quantify the pain (the ICP's actual cost)
- Mid-market procurement cycles run **weeks**, not minutes: RFQ → quote chase → back-and-forth → approval → contract → payment terms.
- Most of that time is **coordination overhead across fragmented suppliers**, not decision-making.
- For AI-native marketplaces, this is the wall: their agents can shortlist vendors but then **hand off to email and humans**, killing the autonomy they were built to deliver.

> Sharp framing for the slide: *"AI can pick the supplier in seconds. It still takes a human three weeks to actually buy from them. We delete those three weeks."*

---

## 3. Initial Customer Profile (one wedge, not "all businesses")

**Land and expand — not "all businesses."**

**Beachhead: AI-forward businesses that procure at volume** — e.g. fast-growing **e-commerce / D2C brands** sourcing inventory and digital-first SMBs with high-volume routine purchasing. They deploy a buyer agent and get autonomous procurement; **we abstract the wallet and USDC entirely** — they fill a request and get a settled, on-chain-verifiable deal, never touching crypto.

Why this wedge (not "all local shops / SMEs"):
- **Tech-forward + high procurement volume** — the value (weeks → minutes, ~90% cheaper PO) lands hardest where buying is frequent.
- **Ready to adopt** — comfortable delegating to software, unlike a shop owner who approves every PO by hand.
- **The demo is literally this** — a business buying inventory autonomously.
- Avoids the "everyone" trap (judges penalize it) and the heaviest adoption friction (a local shop won't manage a wallet or trust autonomous spend).

**Expansion: the agent economy.** As AI-native marketplaces and agent platforms proliferate, AgentTrade becomes the **settlement rail** they integrate via API — riding Gartner's $15T-B2B-agent-spend-by-2028 wave.

**Why blockchain holds for both:** the *supplier* is an independent party that needs a trustless guarantee of payment — escrow + on-chain settlement provides it without an intermediary, regardless of how crypto-savvy the buyer is.

---

## 4. The solution & why now

A complete agent-to-agent commerce stack, already working end-to-end on Algorand Testnet:

- **Discovery** — agents query a supplier registry by category.
- **Negotiation protocol** — structured RFQ → Quote → Counter → Accept, up to 7 rounds, multi-variable (price, delivery, warranty), with priority-driven strategy (cost / speed / quality / balanced).
- **Concurrent orchestration** — the buyer agent negotiates with multiple suppliers simultaneously and plays them off each other.
- **Trustless settlement** — a PyTeal escrow contract locks USDC, anchors the deal-terms hash on-chain, and releases only on verified delivery proof (or refunds the buyer on timeout).

**Why now:** capable tool-calling LLMs (2024–2025) made autonomous multi-step negotiation actually work, and stablecoin settlement (USDC) made on-chain payment riskless to price in. Eighteen months ago neither half was reliable. Both now are.

---

## 5. Why blockchain (the trust argument, not the buzzword)

This is the part most "AI + blockchain" pitches get wrong. Here it's load-bearing:

**Autonomous agents representing different companies have no inherent basis to trust each other.** A human deal relies on contracts, legal recourse, and reputation built over years. Two agents have none of that. So you need a **neutral enforcement layer that neither party controls**:

- Funds are locked before delivery — the supplier knows they'll be paid.
- Payment releases **only on cryptographic delivery proof** — the buyer knows they won't be rugged.
- The agreement is hashed and anchored on-chain — neither side can later dispute the terms.
- No marketplace or bank sits in the middle taking custody or a rent.

> The insight: **blockchain replaces intermediated trust in autonomous commerce.** It's not decoration — it's the only way two untrusting agents can transact without a human or a platform as referee.

### Comparison slide

| | Traditional / current procurement | AgentTrade |
|---|---|---|
| Negotiation | Human email back-and-forth | Autonomous multi-round agent negotiation |
| Trust source | Legal contracts, marketplace as intermediary | Cryptographic escrow, no intermediary |
| Settlement | Net-30 invoicing, bank rails | USDC escrow, auto-release on proof |
| Dispute protection | Lawyers, chargebacks | Programmable refund on timeout |
| Speed | Days to weeks | Minutes |
| Auditability | Scattered emails/PDFs | On-chain deal + delivery hashes |

---

## 6. How it works (grounded, 60-second version)

1. Buyer submits a structured request (item, qty, budget, deadline, priority) — one form, no free text.
2. The autonomous buyer agent (LangGraph ReAct, 8 tools) discovers suppliers and fires **concurrent RFQs**.
3. It scores quotes with priority-weighted weights and **negotiates up to 7 rounds** with the top suppliers, trading variables when price is stuck.
4. It accepts the best offer **within budget** and calls `lock_escrow`: a group transaction transfers USDC into the contract and anchors the SHA-256 deal hash on-chain.
5. Supplier submits a delivery-proof hash → contract goes `DELIVERED` → payment **auto-releases** to the supplier (`COMPLETED`), or the buyer reclaims funds after the deadline (`REFUNDED`).
6. Every round is persisted off-chain (full audit trail); every state transition is verifiable on the Algorand explorer.

Every supplier type — deterministic bot, LLM-powered, or human-in-the-loop — speaks the **same `SupplierInterface`**, so the buyer agent doesn't know or care who's on the other side. That's the protocol moat.

---

## 7. Revenue model

The strongest version of our monetization is that **the take-rate is programmable into the settlement contract itself** — we don't have to chase invoices, we collect at the moment of on-chain release.

**Short-term — SaaS + settlement fee (primary)**
- Platform subscription: **$99–$499/mo** *(est.)* per buyer org (agent hosting, supplier registry access, dashboards).
- **0.5–1% escrow settlement fee**, enforced on-chain at `release` — when the contract pays the supplier, it routes the fee to the platform wallet in the same transaction. No collections risk, no leakage.

**Mid-term — supplier-side marketplace monetization**
- Verified-supplier badges, priority ranking in discovery, listing fees. (Two-sided: buyers pay to transact, suppliers pay for distribution.)

**Enterprise — infrastructure licensing**
- Private deployments, ERP integrations, custom procurement agents. Annual contracts.

> Why the settlement fee is defensible: because we *are* the escrow, the fee is structurally unavoidable for any deal that wants the trust guarantee. Workflow-automation competitors can't charge a settlement fee — they don't touch the money.
>
> ⚠️ *Status: not yet implemented in the contract. Today `release` transfers the full amount to the seller ([contracts/escrow.py](contracts/escrow.py)). Adding a platform-fee output at release is ~10 lines of PyTeal and makes this revenue story demonstrable rather than claimed.*

---

## 8. Market

Layered, conservative — concentric circles, not one inflated TAM. Full model + sources in [BUSINESS_CASE.md](BUSINESS_CASE.md).

- **TAM** — Gartner: AI agents will intermediate **>$15T of B2B spend by 2028**; at our 0.5–1% settlement take-rate that's a **$75–150B fee pool**.
- **Adjacent context** — procurement software **~$9.8B (2025) → ~$15.8B by 2030** (~10% CAGR, Mordor Intelligence) — cited for context, not our beachhead.
- **SAM** — AI-native B2B marketplaces / agent platforms running buying agents; rides the agentic-commerce market (**~$5.7B in 2025, ~36% CAGR**, Grand View Research).
- **SOM (bottoms-up)** — **~$370K ARR from 50 design-partner orgs in 18 months** (SaaS + settlement fee); ~$5.8M ARR at 300 orgs in year 3.

> Framing for judges: "We're not chasing 1% of global commerce. We want the **first 0.1% of the agent-mediated B2B wave** — 0.1% of Gartner's $15T is $15B settled GMV → ~$112M revenue at 0.75%."

---

## 9. Competitive positioning

| Player | What they do | Gap we fill |
|---|---|---|
| **SAP Ariba / Coupa** | Enterprise procurement suites — workflow, approvals, catalogs | Automate *process*, not negotiation or settlement; require humans in the loop |
| **AI procurement startups** (Zip, Tropic, Levelpath class) | Intake-to-procure, AI-assisted approvals & spend | Still human-decision; no agent-to-agent negotiation, no trustless settlement |
| **B2B marketplaces** (Tradewheel etc.) | Match buyers/suppliers, act as intermediary | They *are* the trusted middleman taking custody/rent; not autonomous, not trustless |
| **Crypto escrow / payment rails** | On-chain payment & escrow primitives | Payment only — no discovery, no negotiation, no agent layer |

**Our one-line wedge:** *Competitors automate the procurement workflow. AgentTrade automates the negotiation and the settlement — the two steps that still require a human or an intermediary.*

No one else combines **autonomous negotiation + multi-agent orchestration + cryptographic escrow settlement.** That triple is the defensible position.

---

## 10. Traction / what's actually built

Be honest and specific — this is a working MVP, and saying so precisely beats vague hype:

- ✅ End-to-end autonomous flow: form → discovery → concurrent negotiation → escrow lock → delivery proof → release, **running on Algorand Testnet** (escrow app + mock USDC ASA deployed).
- ✅ LangGraph ReAct buyer agent with 8 real tools and multi-provider LLM failover (DigitalOcean GenAI / Groq / Gemini / Anthropic) with API-key rotation.
- ✅ PyTeal escrow contract with full state machine (lock → deliver → release → refund), on-chain integration-tested.
- ✅ Uniform `SupplierInterface` with bot / LLM / human implementations.
- ✅ FastAPI backend + React/TS dashboard with live negotiation timeline and on-chain verification links.
- ✅ Deployed (Dockerized, single image) on DigitalOcean.

> Framing: "This isn't a mockup. A judge can submit a request and watch an agent negotiate and settle a real on-chain transaction in minutes."

---

## 11. Defensibility / moat

- **Protocol position** — owning the `SupplierInterface` standard means every new supplier type plugs into *our* negotiation/settlement layer.
- **Settlement custody = structural take-rate** — because trust flows through our contract, the fee is unavoidable for trust-requiring deals.
- **Two-sided network** — buyers bring deal flow, suppliers bring inventory; each side increases the other's value.
- **Data flywheel** — every negotiation round is logged; over time this trains better buyer/supplier strategies no single-sided competitor can match.

---

## 12. Go-to-market (first 100 users)

- **Channel 1 — AI-agent / AI-commerce communities:** the builders whose agents already need to "finish the purchase." Direct, founder-led outreach + SDK.
- **Channel 2 — Algorand / crypto ecosystem:** grants, ecosystem partners, and hackathon visibility convert into first integrations.
- **Channel 3 — sourcing/procurement operator communities:** for the supplier side, recruit early verified suppliers to seed the registry.

Motion: land 5–10 AI-marketplace integrations via API → each brings recurring deal flow → use that to recruit suppliers → settlement-fee revenue scales with GMV.

---

## 13. Roadmap (6 months)

**Phase 1 (now → 2 mo): production-credible core**
- Structured event streaming (in-process EventBus → SSE/WebSocket), session-scoped state, persistence seam for Postgres.
- Real supplier integrations beyond seeded bots.

**Phase 2 (2 → 4 mo): two-sided platform**
- Supplier onboarding, on-chain reputation, analytics dashboard.

**Phase 3 (4 → 6 mo): enterprise & scale**
- ERP integrations, multi-chain settlement, autonomous *supplier* agents (full agent-to-agent, both sides LLM).

---

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM provider outage / cost | Multi-provider failover already built; local-model roadmap for cost control at scale |
| Algorand RPC / indexer downtime | RPC redundancy; retries; settlement is idempotent on-chain state |
| Long-running negotiation failures | Durable workflow store (LangGraph checkpointer → Postgres) + retry/recovery |
| Supplier non-delivery | Programmable refund-on-timeout is the core contract guarantee |
| Single-tenant demo state today | Known; Phase 1 adds session scoping + persistence (narrated, seam identified) |

---

## 15. The ask / vision

We're building the **settlement layer for the autonomous economy** — the rails that let AI agents not just decide, but *transact*, without a human or an intermediary as referee.

Short term: own the agent-to-agent procurement wedge for AI-native marketplaces. Long term: any time two agents need to exchange value across a trust boundary, they settle on AgentTrade.

> **AgentTrade enables autonomous agents to negotiate, execute, and settle procurement agreements without requiring centralized trust intermediaries.** That is the company.
