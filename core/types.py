"""Shared types for AgentTrade v2.

All dataclasses, enums, and type aliases used across the core protocol,
supplier implementations, and buyer agent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NegotiationPhase(str, Enum):
    """Per-supplier negotiation state."""
    INVITED = "invited"
    QUOTED = "quoted"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class DealPhase(str, Enum):
    """Overall procurement deal state."""
    DISCOVERY = "discovery"
    QUOTING = "quoting"
    NEGOTIATING = "negotiating"
    AGREED = "agreed"
    ESCROW_LOCKED = "escrow_locked"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageType(str, Enum):
    """Types of messages exchanged during negotiation."""
    RFQ = "rfq"
    QUOTE = "quote"
    COUNTER_OFFER = "counter_offer"
    ACCEPTANCE = "acceptance"
    REJECTION = "rejection"


class CounterDecision(str, Enum):
    """Supplier's decision on a counter-offer."""
    ACCEPT = "accept"
    COUNTER = "counter"
    REJECT = "reject"


class Priority(str, Enum):
    """Buyer's procurement priority — drives scoring weights."""
    COST = "cost"
    SPEED = "speed"
    QUALITY = "quality"
    BALANCED = "balanced"


# ---------------------------------------------------------------------------
# Scoring weight tables
# ---------------------------------------------------------------------------

SCORING_WEIGHTS: dict[Priority, dict[str, float]] = {
    Priority.COST:     {"price": 0.60, "delivery": 0.15, "rating": 0.10, "warranty": 0.15},
    Priority.SPEED:    {"price": 0.20, "delivery": 0.50, "rating": 0.15, "warranty": 0.15},
    Priority.QUALITY:  {"price": 0.15, "delivery": 0.15, "rating": 0.35, "warranty": 0.35},
    Priority.BALANCED: {"price": 0.40, "delivery": 0.30, "rating": 0.20, "warranty": 0.10},
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NegotiationTerms:
    """Multi-variable terms exchanged each round."""
    unit_price_usd: float
    quantity: int
    delivery_days: int
    warranty_yrs: float
    payment_terms: str | None = None  # "escrow", "net30", etc.

    def total_usd(self) -> float:
        """Total cost in USD."""
        return self.unit_price_usd * self.quantity


@dataclass
class NegotiationMessage:
    """A single message in a negotiation thread."""
    message_id: str
    rfq_id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    round_number: int
    proposed_terms: NegotiationTerms | None
    natural_language: str
    decision: CounterDecision | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def new_id() -> str:
        """Generate a unique message ID."""
        return f"msg-{uuid.uuid4().hex[:12]}"


@dataclass
class ProcurementRequest:
    """Structured form input from buyer — replaces free-text goal."""
    item: str
    category: str
    quantity: int
    budget_usd: float
    deadline: str                            # ISO 8601 date
    target_price_usd: float | None = None    # Optional hint for agent
    min_warranty_yrs: float = 1.0
    priority: Priority = Priority.BALANCED
    requirements: str = ""

    def scoring_weights(self) -> dict[str, float]:
        """Return scoring weights based on buyer's priority."""
        return SCORING_WEIGHTS[self.priority]


@dataclass
class SupplierProfile:
    """Supplier info loaded from the registry (SQLite)."""
    supplier_id: str
    name: str
    category: str
    wallet_addr: str
    rating: float
    base_cost: float
    margin_pct: float
    lead_days: int
    warranty_yrs: float
    min_price: float


@dataclass
class SupplierNegotiationState:
    """Tracks per-supplier negotiation state."""
    supplier_id: str
    supplier_name: str
    rfq_id: str
    phase: NegotiationPhase = NegotiationPhase.INVITED
    current_round: int = 0
    max_rounds: int = 7
    messages: list[NegotiationMessage] = field(default_factory=list)
    current_terms: NegotiationTerms | None = None
    initial_quote: NegotiationTerms | None = None
    best_offer: NegotiationTerms | None = None
    score: float | None = None
    rating: float = 0.0


@dataclass
class ProcurementContext:
    """Full state the buyer agent operates within."""
    buyer_agent_id: str
    request: ProcurementRequest
    deal_phase: DealPhase = DealPhase.DISCOVERY
    negotiations: dict[str, SupplierNegotiationState] = field(default_factory=dict)
    winning_supplier_id: str | None = None
    deal_id: str | None = None
    usd_to_algo_rate: float | None = None

    @property
    def scoring_weights(self) -> dict[str, float]:
        """Scoring weights derived from buyer's priority."""
        return self.request.scoring_weights()
