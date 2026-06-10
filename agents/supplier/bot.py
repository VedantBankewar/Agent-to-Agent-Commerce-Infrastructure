"""RuleBotSupplier — deterministic supplier using existing tools.

Wraps tools/check_inventory.py, tools/calculate_quote.py, and
tools/evaluate_counter.py behind the SupplierInterface ABC.
Multi-variable negotiation: when price hits floor, trades delivery
or warranty instead.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from core.supplier_interface import SupplierInterface
from core.types import (
    CounterDecision,
    MessageType,
    NegotiationMessage,
    NegotiationTerms,
)
from tools.calculate_quote import calculate_quote
from tools.check_inventory import check_inventory
from utils.logger import get_logger

logger = get_logger("supplier_bot")

DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")
MAX_DISCOUNT_PCT = 8.0
MIN_DELIVERY_DAYS = 3
MAX_WARRANTY_BONUS = 2.0


@dataclass
class _SupplierInfo:
    """Internal supplier profile loaded from SQLite."""
    name: str
    min_price: float
    base_cost: float
    margin_pct: float
    lead_days: int
    warranty_yrs: float
    rating: float


class RuleBotSupplier(SupplierInterface):
    """Deterministic supplier — uses existing pricing/negotiation tools.

    Negotiation logic:
        - Never below price floor (min_price)
        - Max 8% discount from initial quote
        - Multi-variable: when price is stuck, trades delivery (-1d) or warranty (+0.5yr)
        - Rounds 1-3: meet halfway; 4-5: small concessions; 6-7: hold firm
    """

    def __init__(self, supplier_id: str) -> None:
        self.supplier_id = supplier_id
        self._info = self._load_profile()
        self.supplier_name = self._info.name if self._info else supplier_id
        self._initial_price: float | None = None

    def receive_rfq(self, message: NegotiationMessage) -> NegotiationMessage:
        """Handle incoming RFQ. Check inventory and compute quote.

        Args:
            message: The RFQ message from the buyer agent.

        Returns:
            Quote message with proposed terms.
        """
        quantity = message.proposed_terms.quantity if message.proposed_terms else 1
        info = self._info  # supplier profile (may be None if not found)

        # Extract item name from RFQ natural language: "RFQ for 50 x Ergonomic Office Chair. Budget..."
        item = "Unknown"
        nl = message.natural_language
        if " x " in nl:
            item = nl.split(" x ", 1)[1].split(".")[0].strip()
        elif "for " in nl.lower():
            # Fallback: "RFQ for Ergonomic Office Chair"
            after_for = nl.lower().split("for ", 1)[1]
            item = after_for.split(".")[0].strip()
            # Remove leading quantity if present
            parts = item.split(" ", 1)
            if parts[0].isdigit() and len(parts) > 1:
                item = parts[1]

        # Try calculate_quote first (uses inventory + supplier data)
        quote = calculate_quote(
            supplier_id=self.supplier_id,
            item=item,
            quantity=quantity,
        )

        if quote is not None:
            unit_price = quote.unit_price
            delivery_days = quote.delivery_days
            warranty_yrs = quote.warranty_yrs
        elif info:
            # Fallback: compute from supplier base_cost when no inventory match
            unit_price = round(info.base_cost * (1 + info.margin_pct / 100.0), 2)
            delivery_days = info.lead_days
            warranty_yrs = info.warranty_yrs
        else:
            return NegotiationMessage(
                message_id=NegotiationMessage.new_id(),
                rfq_id=message.rfq_id,
                from_agent=self.supplier_id,
                to_agent=message.from_agent,
                message_type=MessageType.QUOTE,
                round_number=1,
                proposed_terms=None,
                natural_language=f"Unable to calculate quote for {item}.",
                decision=CounterDecision.REJECT,
            )

        self._initial_price = unit_price
        total_price = round(unit_price * quantity, 2)

        terms = NegotiationTerms(
            unit_price_usd=unit_price,
            quantity=quantity,
            delivery_days=delivery_days,
            warranty_yrs=warranty_yrs,
        )

        return NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=message.rfq_id,
            from_agent=self.supplier_id,
            to_agent=message.from_agent,
            message_type=MessageType.QUOTE,
            round_number=1,
            proposed_terms=terms,
            natural_language=(
                f"Based on current pricing, we can offer "
                f"{quantity} x {item} at ${unit_price:.2f}/unit "
                f"(${total_price:.2f} total). "
                f"Delivery in {delivery_days} days with {warranty_yrs}yr warranty."
            ),
        )

    def receive_counter(self, message: NegotiationMessage) -> NegotiationMessage:
        """Handle counter-offer with multi-variable negotiation.

        Logic:
            - If buyer's price >= our current price: accept
            - If buyer's price >= max discount floor: negotiate
            - When price hits floor: trade delivery or warranty
            - Early rounds: meet halfway; later rounds: smaller concessions

        Args:
            message: Counter-offer from buyer agent.

        Returns:
            Response with accept/counter/reject and updated terms.
        """
        if not message.proposed_terms:
            return self._reject_message(message, "No terms in counter-offer.")

        info = self._info
        if not info:
            return self._reject_message(message, "Supplier profile not found.")

        proposed = message.proposed_terms
        round_num = message.round_number

        # Initialize initial price if not set (e.g. session restored)
        if self._initial_price is None:
            self._initial_price = info.base_cost * (1 + info.margin_pct / 100.0)

        initial_price = self._initial_price
        price_floor = info.min_price
        max_discount_price = initial_price * (1 - MAX_DISCOUNT_PCT / 100.0)
        floor_price = max(price_floor, max_discount_price)

        # Current supplier terms to work from
        current_delivery = proposed.delivery_days or info.lead_days
        current_warranty = proposed.warranty_yrs or info.warranty_yrs

        # --- Decision logic ---

        # Accept if buyer offers at or above initial price
        if proposed.unit_price_usd >= initial_price:
            return self._accept(message, proposed.unit_price_usd, current_delivery, current_warranty, proposed.quantity)

        # Accept if buyer offers at or above floor and it's a late round
        if proposed.unit_price_usd >= floor_price and round_num >= 4:
            return self._accept(message, proposed.unit_price_usd, current_delivery, current_warranty, proposed.quantity)

        # Reject if below absolute price floor
        if proposed.unit_price_usd < price_floor * 0.9:
            return NegotiationMessage(
                message_id=NegotiationMessage.new_id(),
                rfq_id=message.rfq_id,
                from_agent=self.supplier_id,
                to_agent=message.from_agent,
                message_type=MessageType.COUNTER_OFFER,
                round_number=round_num,
                proposed_terms=NegotiationTerms(
                    unit_price_usd=round(floor_price, 2),
                    quantity=proposed.quantity,
                    delivery_days=current_delivery,
                    warranty_yrs=current_warranty,
                ),
                natural_language=(
                    f"Your offer of ${proposed.unit_price_usd:.2f} is well below our minimum. "
                    f"Our best price is ${floor_price:.2f}/unit."
                ),
                decision=CounterDecision.REJECT,
            )

        # --- Counter-offer logic with multi-variable trades ---
        if proposed.unit_price_usd >= floor_price:
            # Price is acceptable — but try to negotiate
            counter_price = proposed.unit_price_usd
            counter_delivery = current_delivery
            counter_warranty = current_warranty

            # Offer delivery improvement if buyer wants faster
            if proposed.delivery_days < current_delivery and current_delivery > MIN_DELIVERY_DAYS:
                counter_delivery = max(current_delivery - 1, MIN_DELIVERY_DAYS)

            # Offer warranty improvement
            if proposed.warranty_yrs > current_warranty:
                bonus = min(proposed.warranty_yrs - current_warranty, 0.5)
                counter_warranty = current_warranty + bonus
                if counter_warranty > info.warranty_yrs + MAX_WARRANTY_BONUS:
                    counter_warranty = info.warranty_yrs + MAX_WARRANTY_BONUS

            return self._accept(message, counter_price, counter_delivery, counter_warranty, proposed.quantity)

        # Price below floor but above absolute minimum — counter
        if round_num <= 2:
            # Early rounds: meet halfway
            counter_price = (proposed.unit_price_usd + floor_price) / 2.0
        elif round_num <= 4:
            # Mid rounds: small concession from floor
            gap = floor_price - proposed.unit_price_usd
            counter_price = floor_price - (gap * 0.2)
        else:
            # Late rounds: hold firm
            counter_price = floor_price

        counter_price = max(counter_price, price_floor)

        # Multi-variable trades when price is stuck
        counter_delivery = info.lead_days
        counter_warranty = info.warranty_yrs

        if round_num >= 3 and proposed.delivery_days < info.lead_days:
            counter_delivery = max(info.lead_days - 1, MIN_DELIVERY_DAYS)

        if round_num >= 4 and proposed.warranty_yrs > info.warranty_yrs:
            counter_warranty = min(info.warranty_yrs + 0.5, info.warranty_yrs + MAX_WARRANTY_BONUS)

        return NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=message.rfq_id,
            from_agent=self.supplier_id,
            to_agent=message.from_agent,
            message_type=MessageType.COUNTER_OFFER,
            round_number=round_num,
            proposed_terms=NegotiationTerms(
                unit_price_usd=round(counter_price, 2),
                quantity=proposed.quantity,
                delivery_days=counter_delivery,
                warranty_yrs=counter_warranty,
            ),
            natural_language=self._counter_message(round_num, counter_price, counter_delivery, counter_warranty),
            decision=CounterDecision.COUNTER,
        )

    def confirm_deal(self, message: NegotiationMessage) -> NegotiationMessage:
        """Acknowledge accepted deal.

        Args:
            message: Acceptance message from buyer.

        Returns:
            Confirmation message.
        """
        return NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=message.rfq_id,
            from_agent=self.supplier_id,
            to_agent=message.from_agent,
            message_type=MessageType.ACCEPTANCE,
            round_number=message.round_number,
            proposed_terms=message.proposed_terms,
            natural_language=(
                f"Deal confirmed. We'll begin processing your order immediately. "
                f"Expect delivery within {message.proposed_terms.delivery_days} days."
                if message.proposed_terms
                else "Deal confirmed. Thank you for your business."
            ),
            decision=CounterDecision.ACCEPT,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_profile(self) -> _SupplierInfo | None:
        """Load supplier profile from SQLite."""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM suppliers WHERE supplier_id = ?",
                (self.supplier_id,),
            ).fetchone()
            conn.close()

            if row is None:
                return None

            return _SupplierInfo(
                name=row["name"],
                min_price=row["min_price"],
                base_cost=row["base_cost"],
                margin_pct=row["margin_pct"],
                lead_days=row["lead_days"],
                warranty_yrs=row["warranty_yrs"],
                rating=row["rating"],
            )
        except Exception as e:
            logger.error("Failed to load supplier profile", extra={"error": str(e)})
            return None

    def _accept(
        self,
        message: NegotiationMessage,
        price: float,
        delivery: int,
        warranty: float,
        quantity: int,
    ) -> NegotiationMessage:
        """Build an acceptance response."""
        return NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=message.rfq_id,
            from_agent=self.supplier_id,
            to_agent=message.from_agent,
            message_type=MessageType.COUNTER_OFFER,
            round_number=message.round_number,
            proposed_terms=NegotiationTerms(
                unit_price_usd=round(price, 2),
                quantity=quantity,
                delivery_days=delivery,
                warranty_yrs=warranty,
            ),
            natural_language=(
                f"We accept at ${price:.2f}/unit with {delivery}-day delivery "
                f"and {warranty}yr warranty."
            ),
            decision=CounterDecision.ACCEPT,
        )

    def _reject_message(
        self, message: NegotiationMessage, reason: str
    ) -> NegotiationMessage:
        """Build a rejection response."""
        return NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=message.rfq_id,
            from_agent=self.supplier_id,
            to_agent=message.from_agent,
            message_type=MessageType.REJECTION,
            round_number=message.round_number,
            proposed_terms=None,
            natural_language=reason,
            decision=CounterDecision.REJECT,
        )

    @staticmethod
    def _counter_message(
        round_num: int, price: float, delivery: int, warranty: float
    ) -> str:
        """Generate natural language for a counter-offer."""
        if round_num <= 2:
            tone = "We're willing to work with you"
        elif round_num <= 4:
            tone = "We've made significant concessions"
        else:
            tone = "This is very close to our final offer"

        return (
            f"{tone}. Our counter: ${price:.2f}/unit, "
            f"{delivery}-day delivery, {warranty}yr warranty."
        )
