# AgentTrade — Business Case (the 40% panel)

> Deep-dive backing the Business slide + Q&A: a **quantified problem**, a **sourced TAM/SAM/SOM**, **unit economics**, an airtight **why-blockchain**, and a **validation plan**. Drop the bolded numbers into [DECK.md](DECK.md) Slide 2 and [PITCH.md](PITCH.md) §8.
>
> ⚠️ Figures are from public market reports (2025–2026) and vary by source — cite the **conservative** end and name the source. Verify before the event. Sources listed at the bottom.

---

## 1. The problem, quantified (with sources)

Procurement is slow and expensive *because it's manual coordination*, and AI hasn't fixed the closing step.

- **Cost per purchase order:** commonly **$30–60** per PO; CAPS Research pegs the fully-loaded average at **$527** (range $211–$1,688 by industry). Automation drops it to **$5–10**. → *up to ~90% cost reduction* is a defensible claim.
- **Cycle time:** top procurement teams take ~5 hours per PO; **bottom performers ~2 days (48h)** (APQC). Manual PO processing alone is **8–12 hours** of labor. → "weeks across multiple suppliers" is the real-world multi-vendor reality.
- **Invoices:** 43% of firms still process manually at **$15/invoice** vs **$2.36** automated.

**The AI gap (our specific wedge):** today's AI agents *recommend* a supplier, then **hand off to email + humans** to negotiate, contract, and pay. The expensive, slow part — closing — is still manual.

> **One-liner for the slide:** *"A purchase order costs $30–500 and bottom-half teams take 2 days each — and AI still can't close the deal. We make an agent negotiate and settle it in minutes."*

---

## 2. Why now (the wave is real and imminent)

- **Gartner: AI agents will intermediate >$15 TRILLION in B2B spending by 2028.**
- **Gartner: by 2030, ~20% of monetary transactions will be programmable** (autonomous commerce).
- **Agentic-commerce market: ~$5.7B (2025) → ~$65B by 2033, 35.7% CAGR** (Grand View Research).
- **Bain: US agentic commerce $300–500B by 2030** (15–25% of online retail).

> The thesis in one line: **agents are about to transact at $15T scale — and they have no native way to negotiate, trust, and settle with each other. That rail is the company.**

---

## 3. TAM / SAM / SOM (conservative, defensible)

Present as concentric circles, lead with the **bottoms-up SOM** (what judges actually reward):

| Layer | What | Figure (conservative) | Source/logic |
|---|---|---|---|
| **TAM** | Settlement value flowing through agent-mediated B2B commerce | **$15T B2B agent spend by 2028** → at a 0.5–1% settlement take-rate, the *fee pool* is **$75–150B** | Gartner |
| (context) | Procurement software (the tools market we're adjacent to) | **~$9.8B (2025) → ~$15.8B by 2030** (~10% CAGR) | Mordor Intelligence |
| **SAM** | **Beachhead:** AI-forward businesses procuring at volume (e.g. e-commerce/D2C brands) — we abstract the crypto. **Expansion:** AI-native marketplaces/agent platforms integrating the settlement rail | Compounds with the ~36% CAGR agentic-commerce market (~$5.7B in 2025) | Grand View Research |
| **SOM** | What we can win in 18 months | **~$370K ARR from 50 design-partner orgs** (see §4) | bottoms-up (below) |

> **Framing rule (per the judging guide):** *"We're not chasing 1% of global commerce. We want the first 0.1% of the agent-mediated B2B wave."* — 0.1% of Gartner's $15T = **$15B settled GMV → ~$112M revenue** at 0.75%. That's the venture-scale headroom without overselling.

---

## 4. Revenue model + unit economics

**Two streams:** SaaS subscription **+ a 0.5–1% settlement fee enforced on-chain at release** (programmable into the escrow contract — unavoidable for any deal that wants the trust guarantee; workflow-only competitors can't charge it).

**Per-customer/year (conservative):**
- SaaS: ~$300/mo × 12 = **$3,600**
- Settlement: an AI-marketplace buyer settling **$500K GMV/yr × 0.75% = $3,750**
- **≈ $7,350 / customer / yr**

**SOM build:**
- **18 months — 50 design-partner orgs:** SaaS ~$180K + settlement ~$190K = **~$370K ARR**
- **Year 3 — 300 orgs, $2M avg GMV:** SaaS ~$1.3M + settlement (300 × $15K) ~$4.5M = **~$5.8M ARR**
- Mid-term: supplier-side monetization (verified badges, priority ranking, listing fees) adds a second side.

---

## 5. Why blockchain — the three rebuttals you'll be asked

**"Why not a regular DB + API?"** (the guaranteed question)
- A database can *record* a deal; it can't make a supplier's agent **trust an unknown buyer's agent** with payment, or **auto-refund on non-delivery** without a trusted operator. Remove the operator → you need neutral, tamper-proof enforcement: that's escrow + on-chain settlement.
- **Custody = the moat.** Because trust flows through our contract, the **settlement fee is structurally unavoidable**. A DB+API company can't charge it — they never touch the money.

**"Why x402 / why Algorand?"**
- **x402** is the agent-native payment standard (HTTP 402) — purpose-built for machine-to-machine payments, which is exactly agent-to-agent commerce.
- **Algorand:** 4s finality + ~$0.001 fees make frequent micro-settlements economical; Python (PyTeal) matches our agent stack; testnet + USDC for riskless stablecoin settlement.

**"What's actually on-chain vs just hype?"**
- Real: USDC settlement (x402 + escrow), the deal-terms hash, delivery-proof hash, state transitions — all verifiable on the explorer. Off-chain: negotiation transcripts (hash-bridged). Honest, not decorative.

---

## 6. Competitive positioning (sharpened)

| Player | What they do | Why they can't do this |
|---|---|---|
| SAP Ariba / Coupa | Enterprise procurement workflow & approvals | Automate *process*, not negotiation or settlement; human-in-the-loop by design |
| AI procurement startups (Zip / Tropic / Levelpath class) | Intake-to-procure, AI-assisted approvals | Still human-decision; no agent-to-agent negotiation, no trustless settlement |
| B2B marketplaces (Tradewheel etc.) | Match buyers/sellers | They *are* the trusted middleman taking rent; not autonomous |
| Crypto escrow / x402 rails alone | On-chain payment primitives | Payment only — no discovery, negotiation, or agent layer |

**Wedge:** *Competitors automate the workflow. AgentTrade automates the negotiation **and** the settlement — the two steps that still need a human or an intermediary.* No one combines autonomous negotiation + multi-agent orchestration + cryptographic settlement.

---

## 7. Validation — voice-of-customer (secondary) + honest stance

Judges want evidence the pain is real *in human terms*, not just a TAM. We lead with **documented voice-of-customer evidence** — real procurement practitioners, on the record — and are **honest that formal interviews are our immediate next step**, which the judging guide explicitly rewards over fabricated quotes.

**Real practitioner voice (quotable on the slide):**
> *"Before, it was truly Sisyphean work — very frustrating. … It drags on for hours and sometimes days depending on the volume of lines each buyer has."*
> — **Shiri Ashton, Operational Purchase Team Leader, RH Electronics** (on manual email-based supplier procurement)

**Quantified scale of the exact pain we remove (sourced):**
- Procurement staff handle **300–500 supplier emails/week** (Ardent Partners); a mid-size manufacturer ≈ **1,200/week**.
- At ~**4 min/email**, that's ~**80 person-hours/week** — **2 full-time employees** — and ~**$170K/yr** in labor on email handling alone.
- At RH Electronics, **PO distribution took 3 full days** of manual work before automation.
- Pair with §1–§2: **$30–500/PO**, **up to 2-day** cycle time, **Gartner $15T** B2B agent spend by 2028.

**Honest stance (say this verbatim if asked):** *"We haven't run formal customer interviews yet — we've validated through documented voice-of-customer evidence and quantified market data. Our next two weeks are 10 design-partner conversations with e-commerce/D2C and AI-agent teams."* Candor scores; a fabricated "we talked to 20 customers" doesn't.

> Strongest Business-table answer: *"Manual procurement is a documented grind — a purchasing lead at RH Electronics called it 'Sisyphean, very frustrating,' dragging on for days; teams handle 300–500 supplier emails a week, ~2 FTEs of pure email. Gartner says agents will run $15T of B2B spend by 2028 with no way to negotiate or settle. We make an agent close that deal in minutes — and we're booking our first design-partner calls now."*

---

## 8. Infrastructure cost model (margin at scale)  *(Scalability panel)*

Per-deal variable cost is dominated by **LLM tokens**; everything else is near-zero. *(Estimates — verify before citing.)*

**Per procurement run (variable):**
| Item | ~cost/run | Note |
|---|---|---|
| LLM tokens (agent + supplier replies, ~5–10 calls) | **$0.01–0.05** | DO GenAI `gpt-oss-120b`; cheaper/local models for routine rounds |
| Algorand fees (~5–8 txns: deploy/lock/deliver/release) | **$0.001–0.004** | ~0.001 ALGO/txn — negligible |
| Indexer / RPC reads | ~$0 | public nodes / Nodely free tier at low volume |
| **Total / run** | **~$0.01–0.05** | LLM dominates |

**Fixed infra (monthly):**
| Item | ~/mo |
|---|---|
| App host (DigitalOcean droplet) | $12–24 |
| Postgres (managed, when added) | ~$15 |
| Redis (optional) | ~$10 |
| RPC/indexer (paid tier at scale) | $0 → $50+ |
| **Total** | **~$25–100/mo** (scales with tier) |

**Margin (vs the §4 revenue model):**
- Revenue/deal = 0.5–1% settlement fee. On a **$500** deal → **$2.50–5.00**; variable cost ~$0.05 → **>98% gross margin per settlement.**
- SaaS ($99–499/mo) covers fixed infra many times over from a handful of customers.
- **At 10×/100× the margins *improve*:** fixed infra amortizes, blockchain fees stay negligible, and the only per-deal cost (LLM) has a clear cost-down path (local models, round caps, caching). We don't custody inventory or run a marketplace — just the settlement rail, which is structurally high-margin.

> One-liner: *"Each autonomous deal costs us a few cents — mostly LLM — and earns 0.5–1% of GMV on-chain. The unit economics get better at scale, not worse."*

---

## Sources
- Procurement software market — [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/procurement-software-market) · [Precedence Research](https://www.precedenceresearch.com/procurement-software-market) · [Technavio/PRNewswire](https://www.prnewswire.com/news-releases/procurement-software-market-to-grow-by-usd-6-66-billion-2025-2029-boosted-by-e-commerce-and-retail-growth-market-evolution-powered-by-ai---technavio-302369830.html)
- Manual procurement cost & cycle time — [Planergy (PO processing cost)](https://planergy.com/blog/po-processing-cost/) · [Digital Purchase Order](https://www.digitalpurchaseorder.com/post/the-true-cost-of-manual-purchase-orders) · [Profit.co (cycle-time KPI)](https://www.profit.co/blog/kpis-library/leverage-business-with-procurement-cycle-time-kpi/)
- Agentic commerce market & B2B agent spend — [Grand View Research](https://www.grandviewresearch.com/industry-analysis/agentic-commerce-market-report) · [Gartner via DigitalCommerce360 ($15T B2B by 2028)](https://www.digitalcommerce360.com/2025/11/28/gartner-ai-agents-15-trillion-in-b2b-purchases-by-2028/) · [Bain via DigitalCommerce360](https://www.digitalcommerce360.com/2025/12/22/bain-agentic-ai-us-ecommerce-sales-2030/)
