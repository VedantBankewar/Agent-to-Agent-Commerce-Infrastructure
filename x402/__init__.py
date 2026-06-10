"""x402 agent-native payment layer for AgentTrade.

This package adds HTTP-native (x402) USDC settlement on Algorand alongside the
existing escrow contract:

    Buyer agent (x402 client)  ──HTTP──▶  Supplier (x402 server, payment-gated)
                                              │
                                              ▼
                                    Facilitator (verify + settle on Algorand)

x402 = the agent-to-agent payment rail (instant settlement).
Escrow (contracts/) = the delivery-guarantee rail (held funds, release on proof).

The buyer agent chooses the rail per deal. This package is intentionally
decoupled from the live agent tools so it can be developed and tested in
isolation before being wired into the negotiation flow.

See x402/README.md for the install + testnet smoke-test runbook.
"""
