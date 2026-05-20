"""NegotiationSessionManager for AgentTrade v2.

Central orchestrator for all concurrent negotiations within a single
procurement. Manages per-supplier state machines, scoring, and persistence.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from core.events import EventBus
from core.supplier_interface import SupplierRegistry
from core.types import (
    CounterDecision,
    DealPhase,
    MessageType,
    NegotiationMessage,
    NegotiationPhase,
    NegotiationTerms,
    ProcurementContext,
    SupplierNegotiationState,
    SupplierProfile,
)
from utils.logger import get_logger

logger = get_logger("negotiation")

DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")
DEFAULT_MAX_ROUNDS = 7


class NegotiationSessionManager:
    """Orchestrates concurrent multi-supplier negotiations.

    Manages the per-supplier state machine:
        INVITED -> QUOTED -> NEGOTIATING(round N) -> ACCEPTED/REJECTED/EXPIRED

    All rounds are persisted to SQLite negotiation_sessions and
    negotiation_rounds tables for a full audit trail.

    Args:
        context: The ProcurementContext for this procurement run.
        db_path: Path to the SQLite database.
    """

    def __init__(
        self,
        context: ProcurementContext,
        db_path: str = DATABASE_PATH,
    ) -> None:
        self.context = context
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Public API — called by buyer agent tools
    # ------------------------------------------------------------------

    def start_negotiation(
        self,
        supplier: SupplierProfile,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> NegotiationMessage:
        """Send RFQ to a supplier and get their quote back.

        Creates a new negotiation session and transitions the supplier
        from INVITED -> QUOTED.

        Args:
            supplier: Supplier profile from the registry.
            max_rounds: Maximum negotiation rounds allowed.

        Returns:
            The supplier's quote message with proposed terms.
        """
        rfq_id = self.context.request.item.replace(" ", "_").lower()
        rfq_id = f"rfq-{uuid.uuid4().hex[:8]}"

        state = SupplierNegotiationState(
            supplier_id=supplier.supplier_id,
            supplier_name=supplier.name,
            rfq_id=rfq_id,
            phase=NegotiationPhase.INVITED,
            max_rounds=max_rounds,
            rating=supplier.rating,
        )
        self.context.negotiations[supplier.supplier_id] = state

        # Build RFQ message
        rfq_msg = NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=rfq_id,
            from_agent=self.context.buyer_agent_id,
            to_agent=supplier.supplier_id,
            message_type=MessageType.RFQ,
            round_number=0,
            proposed_terms=NegotiationTerms(
                unit_price_usd=self.context.request.target_price_usd or 0.0,
                quantity=self.context.request.quantity,
                delivery_days=0,
                warranty_yrs=self.context.request.min_warranty_yrs,
            ),
            natural_language=(
                f"RFQ for {self.context.request.quantity} x {self.context.request.item}. "
                f"Budget: ${self.context.request.budget_usd:.2f}. "
                f"Deadline: {self.context.request.deadline}."
            ),
        )

        state.messages.append(rfq_msg)
        self._persist_session(state)
        self._persist_round(state, rfq_msg)

        # Send to supplier via the interface
        supplier_impl = SupplierRegistry.get(supplier.supplier_id)
        response = supplier_impl.receive_rfq(rfq_msg)

        # Update state with quote
        state.messages.append(response)
        state.current_round = 1
        state.phase = NegotiationPhase.QUOTED
        state.current_terms = response.proposed_terms
        state.initial_quote = response.proposed_terms
        state.best_offer = response.proposed_terms
        if response.proposed_terms:
            state.score = self._score_terms(response.proposed_terms, supplier.rating)

        self._persist_round(state, response)
        self._update_session_phase(state)

        EventBus.emit("quote_received", {
            "supplier_id": supplier.supplier_id,
            "supplier_name": supplier.name,
            "terms": self._terms_to_dict(response.proposed_terms),
            "score": state.score,
        })

        logger.info(
            "Quote received",
            extra={
                "supplier_id": supplier.supplier_id,
                "rfq_id": rfq_id,
                "unit_price": response.proposed_terms.unit_price_usd if response.proposed_terms else None,
            },
        )

        return response

    def send_counter(
        self,
        supplier_id: str,
        terms: NegotiationTerms,
        reasoning: str,
    ) -> NegotiationMessage:
        """Send a counter-offer to a supplier.

        Transitions the supplier from QUOTED/NEGOTIATING to
        NEGOTIATING(round+1), ACCEPTED, or REJECTED.

        Args:
            supplier_id: The supplier to counter.
            terms: The proposed counter-terms.
            reasoning: Natural language reasoning for the counter.

        Returns:
            The supplier's response message.
        """
        state = self._get_state(supplier_id)

        if state.phase not in (NegotiationPhase.QUOTED, NegotiationPhase.NEGOTIATING):
            raise ValueError(
                f"Cannot counter supplier {supplier_id} in phase {state.phase}"
            )

        if state.current_round >= state.max_rounds:
            raise ValueError(
                f"Max rounds ({state.max_rounds}) reached for supplier {supplier_id}"
            )

        counter_msg = NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=state.rfq_id,
            from_agent=self.context.buyer_agent_id,
            to_agent=supplier_id,
            message_type=MessageType.COUNTER_OFFER,
            round_number=state.current_round + 1,
            proposed_terms=terms,
            natural_language=reasoning,
        )
        state.messages.append(counter_msg)
        self._persist_round(state, counter_msg)

        EventBus.emit("counter_sent", {
            "supplier_id": supplier_id,
            "round": counter_msg.round_number,
            "proposed_terms": self._terms_to_dict(terms),
            "reasoning": reasoning,
        })

        # Get supplier response
        supplier_impl = SupplierRegistry.get(supplier_id)
        response = supplier_impl.receive_counter(counter_msg)

        state.messages.append(response)
        state.current_round = counter_msg.round_number
        state.current_terms = response.proposed_terms or state.current_terms
        self._persist_round(state, response)

        # Update state based on decision
        if response.decision == CounterDecision.ACCEPT:
            state.phase = NegotiationPhase.ACCEPTED
            state.best_offer = response.proposed_terms or state.current_terms
        elif response.decision == CounterDecision.REJECT:
            state.phase = NegotiationPhase.REJECTED
        else:
            state.phase = NegotiationPhase.NEGOTIATING
            if response.proposed_terms:
                current_score = self._score_terms(response.proposed_terms, state.rating)
                best_score = self._score_terms(state.best_offer, state.rating) if state.best_offer else 0
                if current_score > best_score:
                    state.best_offer = response.proposed_terms

        state.score = self._score_terms(
            state.best_offer, state.rating
        ) if state.best_offer else None

        self._update_session_phase(state)

        EventBus.emit("counter_received", {
            "supplier_id": supplier_id,
            "round": state.current_round,
            "decision": response.decision.value if response.decision else None,
            "response_terms": self._terms_to_dict(response.proposed_terms),
            "supplier_message": response.natural_language,
        })

        logger.info(
            "Counter response received",
            extra={
                "supplier_id": supplier_id,
                "round": state.current_round,
                "decision": response.decision.value if response.decision else None,
            },
        )

        return response

    def accept_offer(self, supplier_id: str) -> NegotiationMessage:
        """Accept the current terms from a supplier.

        Args:
            supplier_id: The supplier whose offer to accept.

        Returns:
            Confirmation message from the supplier.
        """
        state = self._get_state(supplier_id)

        accept_msg = NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=state.rfq_id,
            from_agent=self.context.buyer_agent_id,
            to_agent=supplier_id,
            message_type=MessageType.ACCEPTANCE,
            round_number=state.current_round,
            proposed_terms=state.current_terms,
            natural_language="We accept your terms. Proceeding to escrow.",
            decision=CounterDecision.ACCEPT,
        )
        state.messages.append(accept_msg)
        state.phase = NegotiationPhase.ACCEPTED
        state.best_offer = state.current_terms

        self._persist_round(state, accept_msg)
        self._update_session_phase(state)

        # Notify supplier
        supplier_impl = SupplierRegistry.get(supplier_id)
        confirmation = supplier_impl.confirm_deal(accept_msg)
        state.messages.append(confirmation)
        self._persist_round(state, confirmation)

        EventBus.emit("offer_accepted", {
            "supplier_id": supplier_id,
            "supplier_name": state.supplier_name,
            "final_terms": self._terms_to_dict(state.best_offer),
        })

        logger.info(
            "Offer accepted",
            extra={"supplier_id": supplier_id, "rfq_id": state.rfq_id},
        )

        return confirmation

    def reject_supplier(self, supplier_id: str, reason: str) -> None:
        """Walk away from a supplier negotiation.

        Args:
            supplier_id: The supplier to reject.
            reason: Why the agent is walking away.
        """
        state = self._get_state(supplier_id)

        reject_msg = NegotiationMessage(
            message_id=NegotiationMessage.new_id(),
            rfq_id=state.rfq_id,
            from_agent=self.context.buyer_agent_id,
            to_agent=supplier_id,
            message_type=MessageType.REJECTION,
            round_number=state.current_round,
            proposed_terms=None,
            natural_language=reason,
            decision=CounterDecision.REJECT,
        )
        state.messages.append(reject_msg)
        state.phase = NegotiationPhase.REJECTED

        self._persist_round(state, reject_msg)
        self._update_session_phase(state)

        EventBus.emit("supplier_rejected", {
            "supplier_id": supplier_id,
            "supplier_name": state.supplier_name,
            "reason": reason,
        })

        logger.info(
            "Supplier rejected",
            extra={"supplier_id": supplier_id, "reason": reason},
        )

    def get_status(self) -> dict[str, Any]:
        """Return current state of all negotiations.

        Returns:
            Dict with deal_phase and per-supplier negotiation states.
        """
        return {
            "deal_phase": self.context.deal_phase.value,
            "negotiations": {
                sid: {
                    "supplier_name": s.supplier_name,
                    "phase": s.phase.value,
                    "round": s.current_round,
                    "max_rounds": s.max_rounds,
                    "current_terms": self._terms_to_dict(s.current_terms),
                    "best_offer": self._terms_to_dict(s.best_offer),
                    "score": s.score,
                }
                for sid, s in self.context.negotiations.items()
            },
        }

    def get_best_offers(self) -> list[tuple[str, NegotiationTerms, float]]:
        """Return active negotiations sorted by score (descending).

        Returns:
            List of (supplier_id, best_terms, score) tuples.
        """
        results = []
        for sid, state in self.context.negotiations.items():
            if state.phase in (
                NegotiationPhase.QUOTED,
                NegotiationPhase.NEGOTIATING,
                NegotiationPhase.ACCEPTED,
            ) and state.best_offer and state.score is not None:
                results.append((sid, state.best_offer, state.score))

        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def start_negotiations_concurrent(
        self,
        suppliers: list[SupplierProfile],
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> dict[str, NegotiationMessage]:
        """Send RFQs to multiple suppliers concurrently.

        Args:
            suppliers: List of supplier profiles to contact.
            max_rounds: Maximum rounds per supplier.

        Returns:
            Dict mapping supplier_id to their quote response.
        """
        results: dict[str, NegotiationMessage] = {}

        with ThreadPoolExecutor(max_workers=min(len(suppliers), 5)) as executor:
            futures = {
                executor.submit(self.start_negotiation, s, max_rounds): s
                for s in suppliers
            }
            for future in as_completed(futures):
                supplier = futures[future]
                try:
                    response = future.result()
                    results[supplier.supplier_id] = response
                except Exception as e:
                    logger.error(
                        "Failed to get quote",
                        extra={"supplier_id": supplier.supplier_id, "error": str(e)},
                    )

        return results

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_terms(
        self,
        terms: NegotiationTerms,
        supplier_rating: float,
    ) -> float:
        """Score terms using priority-weighted formula.

        Args:
            terms: The terms to score.
            supplier_rating: The supplier's rating (0-5).

        Returns:
            Weighted score (0-100 scale).
        """
        weights = self.context.scoring_weights

        # Get reference values from all active negotiations
        all_terms = [
            s.best_offer or s.current_terms
            for s in self.context.negotiations.values()
            if s.best_offer or s.current_terms
        ]

        if not all_terms:
            return 50.0

        min_price = min(t.unit_price_usd for t in all_terms if t)
        min_days = min(t.delivery_days for t in all_terms if t and t.delivery_days > 0) or 1
        max_rating = 5.0
        max_warranty = max(t.warranty_yrs for t in all_terms if t) or 1.0

        price_score = (min_price / terms.unit_price_usd * 100) if terms.unit_price_usd > 0 else 0
        delivery_score = (min_days / terms.delivery_days * 100) if terms.delivery_days > 0 else 0
        rating_score = (supplier_rating / max_rating) * 100
        warranty_score = (terms.warranty_yrs / max_warranty) * 100

        total = (
            price_score * weights["price"]
            + delivery_score * weights["delivery"]
            + rating_score * weights["rating"]
            + warranty_score * weights["warranty"]
        )

        return round(total, 2)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_session(self, state: SupplierNegotiationState) -> None:
        """Insert a new negotiation session record."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT OR IGNORE INTO negotiation_sessions
                   (session_id, rfq_id, supplier_id, buyer_id, phase,
                    current_round, max_rounds, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"ns-{uuid.uuid4().hex[:12]}",
                    state.rfq_id,
                    state.supplier_id,
                    self.context.buyer_agent_id,
                    state.phase.value,
                    state.current_round,
                    state.max_rounds,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to persist session", extra={"error": str(e)})

    def _persist_round(
        self, state: SupplierNegotiationState, msg: NegotiationMessage
    ) -> None:
        """Insert a negotiation round record."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT INTO negotiation_rounds
                   (round_id, session_id, round_number, from_agent, to_agent,
                    message_type, unit_price_usd, quantity, delivery_days,
                    warranty_yrs, decision, natural_language, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg.message_id,
                    self._get_session_id(state),
                    msg.round_number,
                    msg.from_agent,
                    msg.to_agent,
                    msg.message_type.value,
                    msg.proposed_terms.unit_price_usd if msg.proposed_terms else None,
                    msg.proposed_terms.quantity if msg.proposed_terms else None,
                    msg.proposed_terms.delivery_days if msg.proposed_terms else None,
                    msg.proposed_terms.warranty_yrs if msg.proposed_terms else None,
                    msg.decision.value if msg.decision else None,
                    msg.natural_language,
                    msg.timestamp,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to persist round", extra={"error": str(e)})

    def _update_session_phase(self, state: SupplierNegotiationState) -> None:
        """Update the session phase and round in the database."""
        try:
            session_id = self._get_session_id(state)
            if not session_id:
                return
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """UPDATE negotiation_sessions
                   SET phase = ?, current_round = ?,
                       updated_at = ?
                   WHERE session_id = ?""",
                (
                    state.phase.value,
                    state.current_round,
                    datetime.now(timezone.utc).isoformat(),
                    session_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to update session", extra={"error": str(e)})

    def _get_session_id(self, state: SupplierNegotiationState) -> str | None:
        """Look up the session_id for a supplier's negotiation."""
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT session_id FROM negotiation_sessions WHERE rfq_id = ? AND supplier_id = ?",
                (state.rfq_id, state.supplier_id),
            ).fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_state(self, supplier_id: str) -> SupplierNegotiationState:
        """Get the negotiation state for a supplier."""
        if supplier_id not in self.context.negotiations:
            raise ValueError(f"No active negotiation with supplier {supplier_id}")
        return self.context.negotiations[supplier_id]

    @staticmethod
    def _terms_to_dict(terms: NegotiationTerms | None) -> dict[str, Any] | None:
        """Convert NegotiationTerms to a JSON-serializable dict."""
        if terms is None:
            return None
        return {
            "unit_price_usd": terms.unit_price_usd,
            "quantity": terms.quantity,
            "delivery_days": terms.delivery_days,
            "warranty_yrs": terms.warranty_yrs,
            "total_usd": terms.total_usd(),
            "payment_terms": terms.payment_terms,
        }
