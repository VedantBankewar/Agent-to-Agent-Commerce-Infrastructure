# AgentTrade — Escrow Smart Contract

> The trust backbone of AgentTrade. A PyTeal contract on the Algorand Virtual Machine
> (AVM) that locks USDC, anchors a deal hash on-chain, and releases or refunds payment
> without any human involvement.

Source: [`contracts/escrow.py`](contracts/escrow.py) ·
Deploy: [`contracts/deploy.py`](contracts/deploy.py) ·
Call helpers: [`contracts/interact.py`](contracts/interact.py)

For where the contract fits in the wider system, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. State Machine

```
IDLE → LOCKED → DELIVERED → COMPLETED
                          ↘ REFUNDED (on timeout)
```

| Value | State | Meaning |
|---|---|---|
| `0` | IDLE | Deployed, no deal locked |
| `1` | LOCKED | USDC locked, awaiting delivery |
| `2` | DELIVERED | Delivery proof submitted |
| `3` | COMPLETED | Payment released to supplier |
| `4` | REFUNDED | Deadline passed, USDC returned to buyer |

---

## 2. On-chain Global State

The contract stores deal state in 8 global keys (schema: 4 uints, 7 byte-slices).

| Key | Type | Contents |
|---|---|---|
| `s` | uint64 | State value (0–4, see above) |
| `b` | bytes | Buyer Algorand address (32-byte raw public key) |
| `u` | bytes | Supplier Algorand address (32-byte raw public key) |
| `a` | uint64 | Escrow amount in micro-USDC (6 decimals) |
| `h` | bytes | SHA-256 deal terms hash (`sha256:...`) |
| `d` | uint64 | Delivery deadline as a Unix timestamp |
| `p` | bytes | SHA-256 delivery proof hash |
| `t` | uint64 | USDC ASA ID (the settlement token) |

No large data is ever stored on-chain — only hashes (the Hash Bridge Pattern).

---

## 3. Contract Operations

Operations are dispatched on the first application argument (`app_args[0]`).
App creation (a NoOp call with no args) is always approved.

### `optin_asset` — creator only

Opts the contract account into the USDC ASA so it can receive transfers. Must run
once after deployment, while the contract is `IDLE`.

- `app_args[1]` = ASA ID (big-endian uint64)
- Stores the ASA ID in key `t`, then submits an inner 0-amount asset transfer to self.

### `lock` — buyer

Locks the buyer's USDC and records the deal. Submitted as a **2-transaction group**:

```
gtxn[0] = AssetTransfer (USDC)  buyer → contract address
gtxn[1] = AppCall  lock(seller, deal_hash, deadline_ts)
```

- `app_args[1]` = seller address · `app_args[2]` = deal hash · `app_args[3]` = deadline (uint64)
- Asserts: `gtxn[0]` is an AssetTransfer of the configured USDC ASA, to this contract,
  for a positive amount, and the contract is `IDLE`.
- Records buyer, seller, amount, hash, deadline → state becomes **LOCKED**.

### `deliver` — supplier only

- `app_args[1]` = delivery proof hash
- Asserts state is `LOCKED` and the caller is the recorded seller.
- Stores the proof hash → state becomes **DELIVERED**.

### `release` — permissionless

- Asserts state is `DELIVERED` (anyone may call).
- Submits an inner USDC transfer of the full amount to the seller → state **COMPLETED**.

### `refund` — buyer only

- Asserts state is `LOCKED`, the caller is the buyer, and the deadline has passed.
- Submits an inner USDC transfer of the full amount back to the buyer → state **REFUNDED**.

### `get_state` — read-only

Returns the current state value for off-chain queries.

---

## 4. Lifecycle Permissions

| Operation | Caller | Precondition |
|---|---|---|
| `optin_asset` | Creator | State IDLE |
| `lock` | Buyer | State IDLE + valid USDC group txn |
| `deliver` | Supplier | State LOCKED |
| `release` | Anyone (permissionless) | State DELIVERED |
| `refund` | Buyer | State LOCKED + deadline passed |
| `UpdateApplication` | Creator only | — |
| `DeleteApplication` | Creator only | State IDLE, COMPLETED, or REFUNDED |

---

## 5. Security Properties

- **No premature release** — `release` requires `DELIVERED`; the supplier cannot be
  paid before submitting a delivery proof.
- **Buyer protection** — if the supplier never delivers, the buyer reclaims the full
  amount via `refund` once the deadline passes.
- **Asset integrity** — `lock` verifies the incoming transfer is exactly the configured
  USDC ASA, addressed to the contract, for a positive amount.
- **Caller checks** — `deliver` and `refund` validate the caller against the recorded
  seller / buyer; `optin_asset` and admin operations are creator-gated.
- **Deterministic settlement** — `release` and `refund` always move the full recorded
  amount via inner transactions; no partial or arbitrary payouts are possible.

---

## 6. Compilation & Deployment

- Authored in **PyTeal 0.26.1**, compiled to **TEAL v8** for the AVM.
- `python contracts/escrow.py` compiles and writes
  `contracts/escrow_approval.teal` and `contracts/escrow_clear.teal`.
- `python contracts/deploy.py` creates the application on Algorand Testnet, funds its
  minimum balance, opts it into the USDC ASA, and writes
  `contracts/deploy_config.json` (`app_id`, contract `address`, `usdc_asset_id`,
  `confirmed_round`).

### Deployed instance (Algorand Testnet)

| Field | Value |
|---|---|
| App ID | `762941405` |
| Contract address | `X2FARGCDXESDLAMOOKEXGX5BMVQYXJ5H6QVOFKUY5RNB7TDS4BASGH5QIU` |
| USDC ASA | `10458941` |
| Network | Algorand Testnet |
| Explorer | https://lora.algokit.io/testnet/application/762941405 |

> The escrow is a singleton (one active deal per instance) and is redeployed for a
> clean run, so the App ID changes per deployment. `contracts/deploy_config.json` and
> `.env` `ESCROW_APP_ID` always hold the current instance.

---

## 7. USD / USDC Settlement

- All UI, agent, and database logic is denominated in **USD**.
- On-chain settlement uses **USDC** (an Algorand Standard Asset) at **1:1 with USD** —
  no conversion or exchange-rate risk.
- The contract operates internally in **micro-USDC** (6 decimals).
- **ALGO** is still required to pay Algorand transaction fees.
