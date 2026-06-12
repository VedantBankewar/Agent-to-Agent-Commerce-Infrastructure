# AgentTrade — Semifinal Deck (Algorand Bharat template)

> Mapped to the official **AlgoBharat Hack Series 3.0** template (≤5 slides, one per criterion).
> **DO NOT touch the branding** — keep the Algorand Bharat logo, blue accent, fonts, and footer.
> Bullet style (per template): **`/` = primary bullet** (blue accent) · **`●` = secondary**.
> Footer on every content slide: `[Team Name]   ·   AlgoBharat Hack Series 3.0   ·   <page #>`.
> `[bracketed]` = founder must fill (see [FOUNDER_TODO.md](FOUNDER_TODO.md)). Presenter notes + the 3 table tracks are **below the slides** (not on them). Full narrative: [PITCH.md](PITCH.md).

---

## SLIDE 1 — Title

- **Project Name:** AgentTrade
- **Team Name:** [Team Name]
- [Team Member 1]
- [Team Member 2]

*(If a one-line tagline fits under the title: "Autonomous agent-to-agent commerce on Algorand.")*

---

## SLIDE 2 — BUSINESS USE CASE  *(40% table)*

**Title:** Agents can decide. They still can't transact.
**Subtitle:** Business use case — autonomous B2B procurement

A purchase order costs **$30–500** and bottom-half teams take **up to 2 days** each (APQC); across multiple suppliers, procurement runs **weeks**. AI agents recommend a vendor — then hand off to email + humans to negotiate and pay. The expensive step is still manual.

`/` **Why now:** Gartner — **AI agents will run >$15 TRILLION of B2B spend by 2028**; agentic commerce ~**36%/yr** growth. Agents are about to transact at scale with no way to negotiate, trust, or settle.
`/` **Customer (one wedge):** AI-native B2B marketplaces / AI-agent startups already running buying agents
`/` **Value:** weeks → minutes; up to **~90% lower per-PO cost** ($5–10 automated vs $30–500 manual) — and the deal actually *closes*, autonomously
`/` **Why blockchain:** two agents from two firms have *no basis to trust each other* — escrow + on-chain settlement replace the intermediary; a DB can't make a supplier trust an unknown agent or auto-refund on non-delivery. **Custody = an unavoidable take-rate.**
`/` **Revenue:** SaaS $99–499/mo + **0.5–1% settlement fee enforced on-chain at release**
`●` Market: TAM = **$15T agent-B2B by 2028 → $75–150B fee pool**; SOM ~**$370K ARR from 50 design partners** in 18mo. [validation: X of N buyers confirmed — *"[quote]"*]

---

## SLIDE 3 — TECHNICAL  *(30% table)*

**Title:** Two agents negotiate; the chain settles.
**Subtitle:** Technical architecture

> 📊 **Slide visual:** use the diagram from [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) (frontend → backend → agent/protocol → Algorand).

A LangGraph ReAct **buyer agent (8 tools)** discovers suppliers and negotiates concurrently (≤7 rounds, multi-variable price/delivery/warranty), then settles on two complementary rails.

`/` **x402** — agent-native HTTP-402 USDC payment (instant settlement) [validated on testnet: status]
`/` **PyTeal escrow** — lock → deliver → release / timeout-refund (delivery guarantee); *the agent chooses the rail per deal*
`/` **Uniform `SupplierInterface`** — bot / LLM / human suppliers, fully interchangeable
`/` **Reliability** — multi-LLM failover + key rotation · in-process EventBus → typed SSE (no stdout scraping) · on-chain integration tests
`●` Stack: Python · LangGraph · PyTeal/algosdk · FastAPI · React/TS · Algorand Testnet

*One-liner to say aloud: "x402 is how agents pay; escrow is how they guarantee delivery."*

---

## SLIDE 4 — SCALABILITY & EXECUTION  *(30% table — use the "Timeline" layout)*

**Title:** Built to 10×.
**Subtitle:** Scalability, go-to-market & roadmap

`/` **10× architecture:** stateless API tier · agent runs in an async worker pool (durable checkpointer) · **Postgres** (replaces SQLite) · Redis cache
`/` **Data/indexer:** reads via **Algorand Indexer** (Nodely/Algonode) + an escrow/deal read-model — never re-scan chain per request; redundant providers
`/` **Cost:** ~**$0.01–0.05/run** (LLM dominates; Algorand fees negligible) → **>98% gross margin per settlement**; margins *improve* at scale — full model in [BUSINESS_CASE.md](BUSINESS_CASE.md) §8
`/` **First 100 users:** ~30 AI-agent/commerce communities · ~20 Algorand-ecosystem partners · ~50 sourcing/ops (supplier side)

**Timeline blocks (template's 5-node timeline):**
- **Now** — working testnet MVP (x402 + escrow)
- **P1 · 0–2mo** — prod core: typed events, indexer, multi-tenant
- **P2 · 2–4mo** — two-sided: supplier onboarding, reputation
- **P3 · 4–6mo** — ERP + multi-chain + autonomous supplier agents
- **Risk/deps** — LLM failover (built) · RPC/indexer redundancy · KYC/AML acknowledged

---

## SLIDE 5 — Thank you  *(template closing)*

- **Thank you**
- **AgentTrade — the settlement layer for the autonomous economy**
- Live demo + GitHub: [repo URL] · agent-trade.live
- The ask: [grant / pilot partners / intros]
- [your contact / X handle]

---

# Presenter notes & the 3 table tracks

You present the **same product** at 3 tables, 3 min + 2 min Q&A each. Lead with the matching slide, end on the **live demo + repo** (pre-opened). **For the 2-min Q&A at each table, see [QA_PREP.md](QA_PREP.md)** — the brutal questions per panel with crisp, honest answers.

**Technical table:** 30s problem → 60s architecture (8-tool agent + two settlement rails) → **90s live demo + code walkthrough** (open `agents/buyer/` *or* `x402/` + `contracts/escrow.py`). End: "x402 = pay, escrow = guarantee."
- *"Where's x402?"* → show `x402/`: buyer = client, supplier = payment-gated server, our facilitator settles USDC on-chain — textbook use of the agent-native payment standard.
- *"Security?"* → be honest: keys/.env gitignored; single-tenant demo; threat model in SECURITY.md [status]. Honest disclosure scores.
- *"10×?"* → the tiers on Slide 4; say plainly Postgres/queue are *seams in place, migration in P1* — not faked.

**Business table:** 30s the 3-week pain → 30s ICP (one wedge) → 30s why-blockchain (trust custody) → 30s revenue (on-chain fee) → **60s live demo** (agent closes a deal in minutes).
- *"Validated?"* → your 1–2 quotes + the number. **Never say "not yet."**
- *"Why not a DB + API?"* → custody of trust + programmable refund; an operator-run DB is the intermediary we remove.
- *"TAM?"* → conservative: "first slice of agent-mediated B2B," not "1% of global commerce."

**Scalability table:** 30s where it is today (single-tenant MVP, honest) → 90s the 10× tiers + indexer + cost → 30s first-100 (numbers) → 30s roadmap.
- *"Monthly cost / margin at scale?"* → LLM tokens dominate; mitigations + negligible chain fees.
- *"Team?"* → who/why-credible; if newer to blockchain, say so + how you're closing the gap.

---

## ⚠️ Founder must fill before the event  (see [FOUNDER_TODO.md](FOUNDER_TODO.md))
1. **Customer validation** (Slide 2 + Business Q&A) — 5–10 conversations; quotes + ≥1 number. *Highest-leverage gap.*
2. **TAM with a source** (Slide 2).
3. **Team story** (Slide 4 Q&A) + **team names** (Slide 1).
4. **The ask** + repo/contact (Slide 5).
5. **x402 / SECURITY status** (Slide 3) → change to "validated on testnet" after the smoke test passes.
6. **Transcribe into the .pptx template** — ≤5 slides, branding untouched.
