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
MAX_NEGOTIATION_ROUNDS = 2


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
) -> EvaluationResult:
    """
    Evaluate an incoming counter-offer from the procurement agent.

    Negotiation rules (from project spec):
      - Never quote below minimum acceptable price (price_floor)
      - Maximum 8% discount from the initial quoted price
      - Meet halfway on round 1 counter, hold firm after round 2

    Args:
        supplier_id:    The supplier's ID.
        rfq_id:         The RFQ this counter-offer is for.
        counter_price:  The price being offered by the buyer.
        round_number:   Current negotiation round (1 or 2).

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

    if counter_price >= max_acceptable:
        # Within acceptable discount band
        if round_number == 1:
            # Meet halfway on round 1
            counter_unit = (counter_price + max_acceptable) / 2.0
            if counter_unit < price_floor:
                counter_unit = price_floor
            return EvaluationResult(
                decision="counter",
                unit_price=round(counter_unit, 2),
                delivery_days=row["lead_days"],
                warranty_yrs=row["warranty_yrs"],
                message=f"Round 1 counter: {round(counter_unit, 2)} (meeting halfway).",
                round=round_number,
            )
        else:
            # Round 2 — hold firm at max acceptable
            return EvaluationResult(
                decision="counter",
                unit_price=round(max_acceptable, 2),
                delivery_days=row["lead_days"],
                warranty_yrs=row["warranty_yrs"],
                message=f"Round 2 counter: {round(max_acceptable, 2)} (final offer, holding firm).",
                round=round_number,
            )

    # Counter below max acceptable discount
    if round_number > MAX_NEGOTIATION_ROUNDS:
        return EvaluationResult(
            decision="reject",
            unit_price=round(max_acceptable, 2),
            delivery_days=row["lead_days"],
            warranty_yrs=row["warranty_yrs"],
            message=f"Round {round_number}: max negotiation rounds reached. Rejected.",
            round=round_number,
        )

    # Counter too low but rounds remaining — respond with counter
    counter_unit = (counter_price + max_acceptable) / 2.0
    if counter_unit < price_floor:
        counter_unit = price_floor
    return EvaluationResult(
        decision="counter",
        unit_price=round(counter_unit, 2),
        delivery_days=row["lead_days"],
        warranty_yrs=row["warranty_yrs"],
        message=f"Counter too low: suggested {round(counter_unit, 2)}.",
        round=round_number,
    )
