"""HumanSupplier — human-in-the-loop supplier via Redis/API.

Posts negotiation messages to a Redis channel and waits for a human
response within a configurable timeout. If the human doesn't respond,
the negotiation expires.
"""

from __future__ import annotations

import json
import time

from core.supplier_interface import SupplierInterface
from core.types import (
    CounterDecision,
    MessageType,
    NegotiationMessage,
    NegotiationTerms,
)
from utils.logger import get_logger

logger = get_logger("supplier_human")

DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes


class HumanSupplier(SupplierInterface):
    """Human supplier — posts to Redis, waits for human response.

    Messages are posted to Redis channel `negotiation:{supplier_id}:inbox`.
    Human responses are expected on `negotiation:{supplier_id}:response`.

    Args:
        supplier_id: The supplier's unique ID.
        timeout_seconds: How long to wait for a human response.
    """

    def __init__(
        self,
        supplier_id: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.supplier_id = supplier_id
        self.supplier_name = f"Human-{supplier_id}"
        self.timeout_seconds = timeout_seconds

    def receive_rfq(self, message: NegotiationMessage) -> NegotiationMessage:
        """Post RFQ to Redis and wait for human quote.

        Args:
            message: The RFQ message from the buyer.

        Returns:
            Human's quote response, or EXPIRED if timeout.
        """
        return self._post_and_wait(message, "rfq")

    def receive_counter(self, message: NegotiationMessage) -> NegotiationMessage:
        """Post counter-offer to Redis and wait for human response.

        Args:
            message: Counter-offer from the buyer.

        Returns:
            Human's response, or EXPIRED if timeout.
        """
        return self._post_and_wait(message, "counter")

    def confirm_deal(self, message: NegotiationMessage) -> NegotiationMessage:
        """Notify human of deal acceptance.

        Args:
            message: Acceptance message from the buyer.

        Returns:
            Acknowledgment message.
        """
        self._post_to_inbox(message, "deal_confirmed")

        return NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=message.rfq_id,
            from_agent=self.supplier_id,
            to_agent=message.from_agent,
            message_type=MessageType.ACCEPTANCE,
            round_number=message.round_number,
            proposed_terms=message.proposed_terms,
            natural_language="Deal acknowledged. Human supplier has been notified.",
            decision=CounterDecision.ACCEPT,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _post_and_wait(
        self,
        message: NegotiationMessage,
        action: str,
    ) -> NegotiationMessage:
        """Post message to Redis inbox and poll for response.

        Args:
            message: The message to post.
            action: Action type (rfq, counter).

        Returns:
            Human's response or EXPIRED message.
        """
        self._post_to_inbox(message, action)

        # Poll for response
        response_data = self._wait_for_response(message.rfq_id)

        if response_data is None:
            return NegotiationMessage(
                message_id=NegotiationMessage.new_id(),
                rfq_id=message.rfq_id,
                from_agent=self.supplier_id,
                to_agent=message.from_agent,
                message_type=MessageType.REJECTION,
                round_number=message.round_number,
                proposed_terms=None,
                natural_language=f"Human supplier did not respond within {self.timeout_seconds}s. Expired.",
                decision=CounterDecision.REJECT,
            )

        # Parse human response into NegotiationMessage
        return self._parse_response(message, response_data)

    def _post_to_inbox(self, message: NegotiationMessage, action: str) -> None:
        """Post a message to the human's Redis inbox."""
        try:
            from messaging.redis_client import get_redis, MESSAGE_TTL_SECONDS
            r = get_redis()
            key = f"negotiation:{self.supplier_id}:inbox"
            payload = json.dumps({
                "action": action,
                "rfq_id": message.rfq_id,
                "from_agent": message.from_agent,
                "message": message.natural_language,
                "proposed_terms": {
                    "unit_price_usd": message.proposed_terms.unit_price_usd,
                    "quantity": message.proposed_terms.quantity,
                    "delivery_days": message.proposed_terms.delivery_days,
                    "warranty_yrs": message.proposed_terms.warranty_yrs,
                } if message.proposed_terms else None,
                "round": message.round_number,
            })
            r.rpush(key, payload)
            r.expire(key, MESSAGE_TTL_SECONDS)
            logger.info("Posted to human inbox", extra={"supplier_id": self.supplier_id, "action": action})
        except Exception as e:
            logger.error("Failed to post to Redis", extra={"error": str(e)})

    def _wait_for_response(self, rfq_id: str) -> dict | None:
        """Poll Redis for a human response.

        Args:
            rfq_id: The RFQ ID to wait for.

        Returns:
            Parsed response dict, or None if timeout.
        """
        try:
            from messaging.redis_client import get_redis
            r = get_redis()
            key = f"negotiation:{self.supplier_id}:response"
            deadline = time.time() + self.timeout_seconds

            while time.time() < deadline:
                result = r.lpop(key)
                if result:
                    data = json.loads(result)
                    if data.get("rfq_id") == rfq_id:
                        return data
                time.sleep(2)

            return None
        except Exception as e:
            logger.error("Failed to read from Redis", extra={"error": str(e)})
            return None

    def _parse_response(
        self,
        original: NegotiationMessage,
        data: dict,
    ) -> NegotiationMessage:
        """Parse a human response dict into a NegotiationMessage.

        Expected data format:
            {
                "rfq_id": "...",
                "decision": "accept" | "counter" | "reject",
                "unit_price_usd": 250.0,
                "quantity": 50,
                "delivery_days": 7,
                "warranty_yrs": 2.0,
                "message": "Human's natural language response"
            }
        """
        decision_str = data.get("decision", "reject")
        decision = CounterDecision(decision_str)

        terms = None
        if decision != CounterDecision.REJECT and "unit_price_usd" in data:
            terms = NegotiationTerms(
                unit_price_usd=float(data["unit_price_usd"]),
                quantity=int(data.get("quantity", original.proposed_terms.quantity if original.proposed_terms else 1)),
                delivery_days=int(data.get("delivery_days", 7)),
                warranty_yrs=float(data.get("warranty_yrs", 1.0)),
            )

        msg_type = MessageType.QUOTE if original.message_type == MessageType.RFQ else MessageType.COUNTER_OFFER

        return NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=original.rfq_id,
            from_agent=self.supplier_id,
            to_agent=original.from_agent,
            message_type=msg_type,
            round_number=original.round_number,
            proposed_terms=terms,
            natural_language=data.get("message", f"Human supplier decision: {decision_str}"),
            decision=decision,
        )
