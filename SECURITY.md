# Security & Threat Model — AgentTrade

> Honest security posture for an autonomous agent-to-agent settlement system on Algorand Testnet. We list what's enforced by code/contract vs. what's currently trusted, the main attack surfaces with mitigations, and the **known open items** — because for an infrastructure project, *acknowledging* limitations is more credible than hiding them.

---

## 1. Trust model — what enforces what

| Concern | Enforced by | Trusted (not yet enforced) |
|---|---|---|
| Payment can't be taken without delivery | **Escrow contract** — `release` only allowed in `DELIVERED`; funds locked first | — |
| Buyer protected if delivery fails | **Escrow** — `refund` to buyer after deadline | — |
| Deal terms can't be altered after agreement | **On-chain SHA-256 deal hash** (Hash Bridge) | — |
| Only the recorded seller is paid | **Escrow** — `release` pays `KEY_SELLER` from global state | — |
| Budget never exceeded | **Code** — hard budget check + USDC pre-check in `lock_escrow` (not LLM judgment) | — |
| **Delivery actually happened** | — | **Trusted: the supplier submits a proof hash; no oracle verifies real-world delivery (mock for the demo).** |
| Agent identity | Algorand wallet address (on-chain) | No reputation/KYC layer yet |

---

## 2. On-chain contract security (`contracts/escrow.py`)

- **State machine guards:** every operation asserts the contract's state (`lock` requires `IDLE`; `deliver` requires `LOCKED` + `caller == seller`; `release` requires `DELIVERED`; `refund` requires `LOCKED` + `caller == buyer` + deadline passed). This prevents double-lock, release-before-deliver, and double-release.
- **Atomic funding:** `lock` is a 2-txn atomic group `[USDC AssetTransfer → escrow, AppCall lock]`; the contract asserts the transfer is the configured USDC ASA, to the contract address, amount > 0. Funds can't be locked without the matching payment.
- **Permissionless release is safe:** anyone may call `release` once `DELIVERED`, but it only ever pays the seller recorded in global state — so it can't be redirected.
- **Creator-only privileged ops:** `optin_asset` and `DeleteApplication` require `Txn.sender == creator`; delete is only allowed in `IDLE/COMPLETED/REFUNDED`.

---

## 3. Attack surfaces & mitigations

| # | Attack | Vector | Mitigation | Status |
|---|---|---|---|---|
| A1 | **Prompt injection** | A malicious supplier's free-text negotiation message tries to manipulate the buyer LLM into overpaying / accepting bad terms | The buyer's *financial* actions are **code-gated**, not LLM-trusted: hard budget enforcement + on-chain USDC pre-check in `lock_escrow`; the contract independently enforces amount/seller/state | ✅ mitigated (defence-in-depth) |
| A2 | **Fake delivery** | Supplier submits a proof hash without delivering | Refund-on-timeout protects the buyer's funds; but real delivery isn't oracle-verified | ⚠️ **open** — needs a delivery oracle (roadmap) |
| A3 | **Replay / double-spend** | Re-submitting lock/release txns | On-chain state asserts + group atomicity; idempotent state transitions | ✅ mitigated |
| A4 | **Key compromise** | Theft of an agent or deployer key | Keys gitignored (`keys/`, `.env`); `.env` is **volume-mounted, never baked into the Docker image**; mnemonics never logged | ⚠️ partial — demo generates agent keys server-side; production needs a KMS/HSM + per-tenant isolation |
| A5 | **Settlement-fee bypass** | A client routes around the platform fee | The 0.5–1% fee will be enforced **in the contract at `release`** (not implemented yet — final-round item) | ⚠️ planned |
| A6 | **RPC/LLM outage** | Dependency downtime mid-deal | Multi-provider LLM failover + key rotation (built); on-chain state is idempotent so retries are safe; RPC redundancy planned | ✅ / ⚠️ partial |
| A7 | **Tenant data leakage** | One run reads another's data | Single-tenant demo today (DB wiped per run) — **not multi-tenant safe**; session scoping + Postgres is the Phase-1 fix | ⚠️ **open** (known) |

---

## 4. Secret & key handling

- Secrets live in `.env` (gitignored) and are **mounted into the container at runtime** — never committed, never copied into the image.
- Wallet key files live in `keys/` (gitignored).
- `utils/logger.py` and coding standards forbid logging keys/mnemonics/API keys.
- ⚠️ The creator mnemonic controls the deployer wallet (testnet funds only). If it is ever exposed (e.g., pasted in a screenshot), rotate it.

---

## 5. Known open items (honest list)

1. **Delivery verification is mock/trust-based** — no oracle confirms real-world delivery. Buyer is protected by timeout-refund, but a colluding/false "delivered" proof would release funds. *(Roadmap: oracle / logistics integration.)*
2. **Single-tenant demo state** — `db/hackathon.db` is wiped per run; no `org_id`/session isolation yet. *(Roadmap: Phase-1 session scoping + Postgres.)*
3. **On-chain platform fee not yet implemented** — `release` currently pays the full amount to the seller.
4. **No formal contract audit** — the PyTeal escrow is integration-tested on testnet (lock/deliver/release/refund) but has not had a third-party audit. Mainnet would require one.
5. **Server-side agent key generation** — fine for a testnet demo; production needs managed keys.

---

## 6. Regulatory awareness

Autonomous B2B settlement in a stablecoin (USDC) has **KYC/AML implications** for production (onboarding businesses, transaction monitoring, sanctions screening). The testnet demo uses test assets and no real customers, so it's out of scope today — but it's a known requirement for go-to-market, not an afterthought.

---

## Reporting

This is a hackathon project on **Algorand Testnet** (no real funds). For security questions, contact the team via the hackathon channel / the repo. Responsible disclosure appreciated.
