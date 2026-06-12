# Q&A Prep — the questions each table will fire

> 2 minutes of Q&A per table. Don't memorize scripts — internalize the **honest** answer. Per the judging guide's critical reminders: *don't bullshit, be honest about what you don't know, don't oversell, show your work.* `[founder]` = you must fill with real specifics.

---

## 🟦 TECHNICAL TABLE

**"You're doing agent-to-agent payments on Algorand — where's x402?"**
→ Built: a `x402pay/` package (signers, facilitator, supplier server) + a buyer client tool — buyer = x402 client, supplier = payment-gated server, our facilitator settles USDC. The full HTTP-402 path is final-round; **today the demo settles via the escrow contract in USDC**, which is also agent-native. *(Don't oversell — say "the x402 layer is built and the SDK is being wired in.")*

**"How do you verify delivery actually happened?"** *(the honest one)*
→ Honestly: we don't yet — the supplier submits a delivery-proof *hash*; there's no oracle confirming real-world delivery. The buyer is protected by **timeout-refund** (funds return if no proof by the deadline). A delivery oracle is the next step. *(This candor scores — see SECURITY.md.)*

**"How would you handle 10× users?"**
→ Stateless FastAPI tier behind a load balancer · agent runs in an async worker pool (durable checkpointer) · **Postgres** replacing SQLite · **indexer-backed read model** so we never re-scan chain. The seams are in place; the migration is Phase 1. I won't pretend it's done — but I know exactly where the seam is.

**"What's your test coverage?"**
→ The escrow contract is **integration-tested on testnet** (lock → deliver → release, and refund). v2 unit coverage is thin — we prioritized the on-chain integration path because *procurement failures have financial consequences*, so that's where reliability matters most. *(Honest > inflated.)*

**"Walk me through your most critical component."**
→ Open `agents/buyer/tools.py` (the 8 tools) → `core/negotiation.py` (concurrent, scored, persisted negotiation) → `contracts/escrow.py` (the on-chain trust layer). One line: *"x402/escrow is how agents pay; the contract's state machine is how they guarantee delivery."*

**"Any security issues?"**
→ Yes, and they're in SECURITY.md: mock delivery proof, single-tenant demo state, no third-party contract audit yet. Mitigated: budget + USDC checks are **code-gated** (not LLM-trusted), so prompt injection can't make the agent overpay; the contract independently enforces amount/seller/state.

---

## 🟩 BUSINESS TABLE  *(40% — highest)*

**"Why blockchain and not just a database + API?"** *(guaranteed)*
→ A DB can *record* a deal; it can't make a supplier's agent **trust an unknown buyer with payment** or **auto-refund on non-delivery** without a trusted operator. Remove the operator → you need neutral, tamper-proof enforcement: escrow + on-chain settlement. And because trust flows through our contract, the **settlement fee is structurally unavoidable** — a DB+API company can't charge it; they never touch the money.

**"Have you validated this? Who did you talk to?"** *(honest + voice-of-customer — don't fabricate)*
→ *"We haven't run formal interviews yet — we validated through documented voice-of-customer evidence and market data. A purchasing lead at RH Electronics called manual email-based procurement 'Sisyphean, very frustrating — it drags on for days.' Procurement teams handle **300–500 supplier emails a week** — ~2 full-time people on email alone. And Gartner says agents will run **$15T** of B2B spend by 2028 with no way to negotiate or settle. Our next two weeks are 10 design-partner calls with e-commerce/D2C and agent teams."* **Don't claim interviews you didn't do** — the guide rewards this candor; pair real practitioner voice + numbers + your concrete next step.

**"What's your TAM?"**
→ Conservatively: agents will intermediate **$15T B2B spend by 2028 (Gartner)** → at our 0.5–1% take-rate that's a **$75–150B fee pool**. We're not chasing 1% of global commerce — just the **first 0.1% of the agent-mediated wave**, which is already ~$15B GMV → ~$112M revenue.

**"How do you make money?"**
→ SaaS ($99–499/mo) + a **0.5–1% settlement fee enforced on-chain at release** — collected the moment funds move, no invoicing, no leakage. >98% gross margin per settlement.

**"Who exactly is your customer? Not 'everyone.'"**
→ Beachhead: **AI-forward businesses that procure at volume** — e.g. fast-growing e-commerce/D2C brands sourcing inventory. They get autonomous procurement; **we abstract the wallet/USDC** so they never touch crypto. Expansion: AI-native marketplaces & agent platforms integrate us as their **settlement rail** (the $15T agent wave).

**"Why not target all businesses / local shops?"** *(strong challenge — have this ready)*
→ Three adoption walls for a typical local shop: (1) they won't manage a crypto wallet, (2) they won't trust an AI to autonomously spend without oversight, (3) their suppliers aren't on the platform (two-sided cold start). So we start with a **narrow, tech-forward** segment that's *ready* — not "everyone" (which the rubric penalizes). Key point: the **blockchain stays necessary because the *supplier* is the untrusting party**, no matter how crypto-savvy the buyer is — so abstracting crypto for the buyer doesn't weaken the on-chain rationale.

---

## 🟨 SCALABILITY & EXECUTION TABLE

**"What's your monthly cost? What happens to margins at scale?"**
→ ~**$0.01–0.05 per deal** (LLM tokens dominate; Algorand fees are negligible), ~$25–100/mo fixed infra. Margins **improve** at scale — fixed infra amortizes, chain fees stay tiny, and the only per-deal cost (LLM) has a clear cost-down path (cheaper/local models, round caps).

**"How will you fetch blockchain data at scale?"**
→ Through the **Algorand Indexer** (Nodely/Algonode) + a read-model that indexes escrow/deal events once — never re-scanning chain per request — with redundant providers for failover. *(We currently read via algod directly; the indexer path is the scale answer.)*

**"First 100 users — be specific."**
→ ~30 from AI-agent/commerce communities (founder-led + SDK), ~20 from Algorand-ecosystem partners, ~50 suppliers from sourcing communities. Land API integrations → recurring deal flow → settlement-fee revenue scales with GMV.

**"Team — are you new to blockchain?"** `[founder — fill]`
→ Be honest. *"[Who you are, why credible.] We're [newer to / experienced in] blockchain; here's how we're closing the gap: [shipped a working PyTeal escrow + USDC settlement live on testnet]."* The guide explicitly says "we're new to blockchain" is OK if you explain how you'll learn.

**"Regulatory risk?"**
→ Production B2B stablecoin settlement has **KYC/AML** implications (onboarding, monitoring, sanctions). Out of scope for the testnet demo (no real funds/customers) — but a known go-to-market requirement, not an afterthought.

**"Third-party dependencies — what if they fail?"**
→ LLM: multi-provider failover (DO GenAI → Groq → Gemini → Anthropic) + key rotation, already built. RPC/indexer: redundant providers. On-chain state is idempotent, so retries are safe.

---

## 🔴 Universal killers (any table)

**"What's NOT done / your biggest risk?"**
→ Straight answer: delivery is verified by a mock proof (oracle is next), the demo is single-tenant, x402's full path isn't wired yet, and the contract isn't audited. The *core loop* — negotiate → lock USDC → deliver → release — works on-chain today, which is the hard part.

**"Why will you win vs Ariba/Coupa/AI-procurement startups?"**
→ They automate the *workflow*; we automate the *negotiation and the settlement* — the two steps that still need a human or an intermediary. No one else combines autonomous negotiation + multi-agent orchestration + cryptographic settlement.

**If you genuinely don't know:** *"Great question — we haven't figured that out yet."* The guide says that's **more** credible than making something up.
