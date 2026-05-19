"""
evaluate_counter — Supplier agent tool.
Accept / counter / reject logic for incoming counter-offers.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Literal


DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")


# Maximum percentage discount from the initial quote price
MAX_DISCOUNT_PCT = 8.0

# Number of negotiation rounds before the supplier holds firm
# v2: increased from 2 to 7 for deep negotiation
MAX_NEGOTIATION_ROUNDS = 7


@dataclass
class EvaluationResult:
    decision: Literal["accept", "counter", "reject"]
    unit_price: float | None
    delivery_days: int | None
    warranty_yrs: float | None
    message: str
    round: int          # Current round number (1-indexed)


def evaluate_counter(
    supplier_id: str,
    rfq_id: str,
    counter_price: float,
    round_number: int = 1,
    max_rounds: int = MAX_NEGOTIATION_ROUNDS,
    proposed_delivery_days: int | None = None,
    proposed_warranty_yrs: float | None = None,
) -> EvaluationResult:
    """
    Evaluate an incoming counter-offer from the procurement agent.

    Negotiation rules:
      - Never quote below minimum acceptable price (price_floor)
      - Maximum 8% discount from the initial quoted price
      - Rounds 1-2: meet halfway; rounds 3-4: small concessions; 5+: hold firm
      - Multi-variable: when price is stuck, trade delivery or warranty

    Args:
        supplier_id:    The supplier's ID.
        rfq_id:         The RFQ this counter-offer is for.
        counter_price:  The price being offered by the buyer.
        round_number:   Current negotiation round (1-indexed).
        max_rounds:     Maximum rounds allowed (default 7).
        proposed_delivery_days: Buyer's requested delivery days (optional).
        proposed_warranty_yrs:  Buyer's requested warranty years (optional).

    Returns:
        EvaluationResult with decision and updated terms.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch supplier price floor and the most recent accepted/countered quote
    cursor.execute(
        """
        SELECT s.min_price, s.warranty_yrs, s.lead_days,
               q.unit_price AS initial_price
        FROM suppliers s
        LEFT JOIN (
            SELECT rfq_id, supplier_id, unit_price
            FROM quotes
            WHERE rfq_id = ? AND supplier_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        ) q ON q.supplier_id = s.supplier_id
        WHERE s.supplier_id = ?
        """,
        (rfq_id, supplier_id, supplier_id),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return EvaluationResult(
            decision="reject",
            unit_price=None,
            delivery_days=None,
            warranty_yrs=None,
            message=f"Supplier {supplier_id} not found.",
            round=round_number,
        )

    price_floor   = row["min_price"]
    initial_price = row["initial_price"]

    if initial_price is None:
        return EvaluationResult(
            decision="reject",
            unit_price=None,
            delivery_days=None,
            warranty_yrs=None,
            message=f"No quote found for RFQ {rfq_id} from supplier {supplier_id}.",
            round=round_number,
        )

    # Rule: never go below price floor
    if counter_price < price_floor:
        return EvaluationResult(
            decision="reject",
            unit_price=price_floor,
            delivery_days=row["lead_days"],
            warranty_yrs=row["warranty_yrs"],
            message=f"Offer {counter_price} below price floor {price_floor}. Rejected.",
            round=round_number,
        )

    # Rule: max 8% discount from initial
    max_acceptable = initial_price * (1 - MAX_DISCOUNT_PCT / 100.0)

    if counter_price >= initial_price:
        # Accept at or above initial — always acceptable
        return EvaluationResult(
            decision="accept",
            unit_price=counter_price,
            delivery_days=row["lead_days"],
            warranty_yrs=row["warranty_yrs"],
            message=f"Offer accepted at {counter_price}.",
            round=round_number,
        )

    # Determine delivery/warranty values (multi-variable trades)
    base_delivery = row["lead_days"]
    base_warranty = row["warranty_yrs"]
    offer_delivery = base_delivery
    offer_warranty = base_warranty

    # Multi-variable trades: when price is near floor, improve other terms
    if proposed_delivery_days and proposed_delivery_days < base_delivery and round_number >= 3:
        offer_delivery = max(base_delivery - 1, 3)
    if proposed_warranty_yrs and proposed_warranty_yrs > base_warranty and round_number >= 4:
        offer_warranty = min(base_warranty + 0.5, base_warranty + 2.0)

    if counter_price >= max_acceptable:
        # Within acceptable discount band
        if round_number <= 2:
            # Early rounds: meet halfway
            counter_unit = (counter_price + max_acceptable) / 2.0
            if counter_unit < price_floor:
                counter_unit = price_floor
            return EvaluationResult(
                decision="counter",
                unit_price=round(counter_unit, 2),
                delivery_days=offer_delivery,
                warranty_yrs=offer_warranty,
                message=f"Round {round_number} counter: {round(counter_unit, 2)} (meeting halfway).",
                round=round_number,
            )
        elif round_number <= 4:
            # Mid rounds: smaller concession
            gap = max_acceptable - counter_price
            counter_unit = max_acceptable - (gap * 0.3)
            if counter_unit < price_floor:
                counter_unit = price_floor
            return EvaluationResult(
                decision="counter",
                unit_price=round(counter_unit, 2),
                delivery_days=offer_delivery,
                warranty_yrs=offer_warranty,
                message=f"Round {round_number}: {round(counter_unit, 2)} with {offer_delivery}d delivery.",
                round=round_number,
            )
        else:
            # Late rounds: hold firm, accept if close enough
            if counter_price >= max_acceptable * 0.98:
                return EvaluationResult(
                    decision="accept",
                    unit_price=round(counter_price, 2),
                    delivery_days=offer_delivery,
                    warranty_yrs=offer_warranty,
                    message=f"Accepted at {round(counter_price, 2)} — close enough to our target.",
                    round=round_number,
                )
            return EvaluationResult(
                decision="counter",
                unit_price=round(max_acceptable, 2),
                delivery_days=offer_delivery,
                warranty_yrs=offer_warranty,
                message=f"Round {round_number}: holding firm at {round(max_acceptable, 2)}.",
                round=round_number,
            )

    # Counter below max acceptable discount
    if round_number > max_rounds:
        return EvaluationResult(
            decision="reject",
            unit_price=round(max_acceptable, 2),
            delivery_days=offer_delivery,
            warranty_yrs=offer_warranty,
            message=f"Round {round_number}: max negotiation rounds reached. Rejected.",
            round=round_number,
        )

    # Counter too low but rounds remaining — respond with counter
    if round_number <= 2:
        counter_unit = (counter_price + max_acceptable) / 2.0
    elif round_number <= 4:
        counter_unit = max_acceptable - (max_acceptable - counter_price) * 0.2
    else:
        counter_unit = max_acceptable

    if counter_unit < price_floor:
        counter_unit = price_floor
    return EvaluationResult(
        decision="counter",
        unit_price=round(counter_unit, 2),
        delivery_days=offer_delivery,
        warranty_yrs=offer_warranty,
        message=f"Round {round_number}: counter at {round(counter_unit, 2)}.",
        round=round_number,
    )
