"""
Escrow Smart Contract — PyTeal for Algorand AVM (PyTeal 0.26.1)

State machine: IDLE → LOCKED → DELIVERED → COMPLETED
                                          ↘ REFUNDED (on timeout)

On-chain state (global keys):
  s  (uint64) — state value (0=IDLE 1=LOCKED 2=DELIVERED 3=COMPLETED 4=REFUNDED)
  b  (bytes)  — buyer Algorand address
  u  (bytes)  — supplier Algorand address
  a  (uint64) — escrow amount in microALGO
  h  (bytes)  — SHA-256 deal terms hash
  d  (uint64) — delivery deadline as Unix timestamp
  p  (bytes)  — SHA-256 delivery proof hash

Group transaction layout for lock:
  tx[0] = Payment from buyer → escrow contract address
  tx[1] = AppCall to lock(seller, deal_hash, deadline_ts)
"""

from __future__ import annotations

from pyteal import (
    # Control flow
    Seq,
    Cond,
    Return,
    Pop,
    For,
    # Assertions
    Assert,
    If,
    And,
    Or,
    Not,
    # Values
    Int,
    Bytes,
    Len,
    Concat,
    Itob,
    Btoi,
    # Global / app / txn
    App,
    Global,
    Txn,
    Gtxn,
    TxnField,
    TxnType,
    OnComplete,
    InnerTxnBuilder,
    # Address encoding
    Len,
    # Compilation
    compileTeal,
    Mode,
)
from algosdk import encoding


# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

STATE_IDLE      = Int(0)
STATE_LOCKED    = Int(1)
STATE_DELIVERED = Int(2)
STATE_COMPLETED = Int(3)
STATE_REFUNDED  = Int(4)

KEY_STATE  = Bytes("s")
KEY_BUYER  = Bytes("b")
KEY_SELLER = Bytes("u")
KEY_AMOUNT = Bytes("a")
KEY_HASH   = Bytes("h")
KEY_DEADLN = Bytes("d")
KEY_PROOF  = Bytes("p")

# Minimum balance: 0.1 ALGO in microALGO
MBR_MIN = Int(100_000)


# ---------------------------------------------------------------------------
# Helper predicates — plain defs returning Expr (no @Subroutine)
# ---------------------------------------------------------------------------

def is_creator():
    return Txn.sender() == Global.creator_address()


def state_is(expected):
    return App.globalGet(KEY_STATE) == expected


def deadline_passed():
    return Global.latest_timestamp() > App.globalGet(KEY_DEADLN)


def caller_is_buyer():
    return Txn.sender() == App.globalGet(KEY_BUYER)


def caller_is_seller():
    return Txn.sender() == App.globalGet(KEY_SELLER)


# ---------------------------------------------------------------------------
# Approval program
# ---------------------------------------------------------------------------

def approval_program():
    # App creation (NoOp, no args) — just return 1 to approve
    # All real operations require at least one app arg
    on_noop = Seq(
        If(
            Txn.application_args.length() == Int(0),
            Return(Int(1)),  # App creation — always approve
        ),
        Cond(
            [Txn.application_args[0] == Bytes("lock"),
             handle_lock()],
            [Txn.application_args[0] == Bytes("deliver"),
             handle_deliver()],
            [Txn.application_args[0] == Bytes("release"),
             handle_release()],
            [Txn.application_args[0] == Bytes("refund"),
             handle_refund()],
            [Txn.application_args[0] == Bytes("get_state"),
             handle_get_state()],
        ),
        Return(Int(0)),
    )

    return Seq(
        Cond(
            [Txn.on_completion() == OnComplete.OptIn,    Return(Int(1))],
            [Txn.on_completion() == OnComplete.NoOp,     on_noop],
            [Txn.on_completion() == OnComplete.CloseOut, Return(Int(1))],
            [Txn.on_completion() == OnComplete.UpdateApplication,
                Return(is_creator())],
            [Txn.on_completion() == OnComplete.DeleteApplication,
                Return(And(is_creator(),
                           Or(state_is(STATE_IDLE), 
                              state_is(STATE_COMPLETED),
                              state_is(STATE_REFUNDED))))],
        ),
        Return(Int(0)),
    )


# ---------------------------------------------------------------------------
# handle_lock
# Called in a group: [Payment -> escrow, AppCall]
# app_args[1] = seller address (58-char Algorand string address)
# app_args[2] = deal_hash (bytes, "sha256:...")
# app_args[3] = deadline as big-endian uint64 (8 bytes)
# Note: buyer and seller are stored as 32-byte raw public keys (via
# Txn.sender() and Txn.accounts[0]) for consistency with how Algorand
# compares addresses internally.
# ---------------------------------------------------------------------------

def handle_lock():
    return Seq(
        # gtxn[0] must be a payment to this contract
        Assert(Gtxn[0].type_enum() == TxnType.Payment),
        Assert(Gtxn[0].receiver() == Global.current_application_address()),
        # Payment must cover minimum balance
        Assert(Gtxn[0].amount() >= MBR_MIN),
        # Contract must be IDLE
        Assert(state_is(STATE_IDLE)),
        # Record all deal state
        # buyer = sender of the payment tx (32-byte raw key)
        App.globalPut(KEY_STATE,  STATE_LOCKED),
        App.globalPut(KEY_BUYER,  Gtxn[0].sender()),
        # seller = accounts[1] passed in the AppCall (32-byte raw key)
        App.globalPut(KEY_SELLER, Txn.accounts[1]),
        App.globalPut(KEY_AMOUNT, Gtxn[0].amount()),
        App.globalPut(KEY_HASH,   Txn.application_args[2]),
        App.globalPut(KEY_DEADLN, Btoi(Txn.application_args[3])),
        App.globalPut(KEY_PROOF,  Bytes("")),
        Return(Int(1)),
    )


# ---------------------------------------------------------------------------
# handle_deliver
# app_args[1] = delivery_hash (bytes)
# ---------------------------------------------------------------------------

def handle_deliver():
    return Seq(
        Assert(state_is(STATE_LOCKED)),
        Assert(caller_is_seller()),
        App.globalPut(KEY_PROOF, Txn.application_args[1]),
        App.globalPut(KEY_STATE, STATE_DELIVERED),
        Return(Int(1)),
    )


# ---------------------------------------------------------------------------
# handle_release
# Permissionless after DELIVERED — anyone can call
# ---------------------------------------------------------------------------

def handle_release():
    return Seq(
        Assert(state_is(STATE_DELIVERED)),
        # Inner payment to seller
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver:  App.globalGet(KEY_SELLER),
            TxnField.amount:     App.globalGet(KEY_AMOUNT),
        }),
        InnerTxnBuilder.Submit(),
        App.globalPut(KEY_STATE, STATE_COMPLETED),
        Return(Int(1)),
    )


# ---------------------------------------------------------------------------
# handle_refund
# Called by buyer after deadline passes
# ---------------------------------------------------------------------------

def handle_refund():
    return Seq(
        Assert(state_is(STATE_LOCKED)),
        Assert(caller_is_buyer()),
        Assert(deadline_passed()),
        # Inner payment to buyer
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver:  App.globalGet(KEY_BUYER),
            TxnField.amount:     App.globalGet(KEY_AMOUNT),
        }),
        InnerTxnBuilder.Submit(),
        App.globalPut(KEY_STATE, STATE_REFUNDED),
        Return(Int(1)),
    )


# ---------------------------------------------------------------------------
# handle_get_state — readonly query, returns current state
# ---------------------------------------------------------------------------

def handle_get_state():
    return Seq(
        Pop(App.globalGet(KEY_STATE)),
        Return(Int(1)),
    )


# ---------------------------------------------------------------------------
# Clear state program
# ---------------------------------------------------------------------------

def clear_state_program():
    return Int(1)


# ---------------------------------------------------------------------------
# Compile + save TEAL
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    approval = compileTeal(approval_program(), Mode.Application, version=8)
    clear     = compileTeal(clear_state_program(), Mode.Application, version=8)

    print(f"Approval TEAL: {len(approval)} chars ({len(approval.encode())} bytes)")
    print(approval)
    print()
    print(f"Clear TEAL: {len(clear)} chars")
    print(clear)

    with open("contracts/escrow_approval.teal", "w", encoding="utf-8") as f:
        f.write(approval)
    with open("contracts/escrow_clear.teal", "w", encoding="utf-8") as f:
        f.write(clear)

    print()
    print("Saved: contracts/escrow_approval.teal, contracts/escrow_clear.teal")
